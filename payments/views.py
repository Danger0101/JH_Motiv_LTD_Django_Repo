import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.db import transaction, models # ADDED: models for coach query
from django.contrib.auth import get_user_model # ADDED: Better way to get User model
from datetime import timedelta # NEW IMPORT
from decimal import Decimal
from cart.utils import get_or_create_cart, get_cart_summary_data, calculate_discount # Import calculate_discount
from cart.models import Cart
# NEW/UPDATED IMPORTS
from coaching_booking.models import ClientOfferingEnrollment 
from coaching_core.models import Offering
from accounts.models import CoachProfile
from .models import Order, OrderItem, CoachingOrder, Coupon
from products.models import Product, Variant, StockPool
from products.printful_service import PrintfulService
from .services import handle_ecommerce_checkout, handle_coaching_enrollment, handle_payment_intent_checkout
from django.utils import timezone
from django.views.generic import ListView, View
from django.db.models import F, Value, CharField # Import F, Value, and CharField for annotations
from .finance_utils import calculate_coaching_split
from .shipping_utils import calculate_cart_shipping, get_shipping_rates
import logging
import json
import uuid

# Custom imports for email sending
from core.email_utils import send_transactional_email


logger = logging.getLogger(__name__)
User = get_user_model() # Get the user model
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
def checkout_cart_view(request):
    """
    Renders the Single-Page Retail Checkout.
    Creates a Stripe PaymentIntent to power the Address & Payment Elements.
    """
    cart = get_or_create_cart(request)
    if not cart or not cart.items.exists():
        return redirect('cart:cart_detail')
    
    # 1. Get Cart Totals (including coupons)
    summary = get_cart_summary_data(cart)
    # Start with Subtotal (Shipping/Tax added later via JS)
    initial_amount = int(summary['total'] * 100)
    if initial_amount < 50: initial_amount = 50

    try:
        # 2. Create PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=initial_amount,
            currency='gbp',
            metadata={
                'cart_id': cart.id,
                'user_id': request.user.id,
                'product_type': 'ecommerce_cart'
            },
            automatic_payment_methods={'enabled': True},
        )
        
        context = {
            'cart': cart,
            'summary': summary,
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
        }
        return render(request, 'payments/checkout_cart.html', context)
        
    except stripe.error.StripeError as e:
        return render(request, 'payments/error.html', {'error': str(e)})

@require_POST
def checkout_calculate_fees(request):
    """
    API called when Address is entered. 
    Returns Shipping Options, Tax, and New Total.
    """
    try:
        data = json.loads(request.body)
        address = data.get('address', {})
        
        cart = get_or_create_cart(request)
        summary = get_cart_summary_data(cart)
        
        # 1. Calculate Shipping & Tax
        rates, tax_amount = get_shipping_rates(address, cart)
        
        # 2. Format Response
        response_data = {
            'rates': [],
            'tax_amount': f"{tax_amount:.2f}",
            'subtotal': f"{summary['total']:.2f}"
        }
        
        for rate in rates:
            # Calculate what the total WOULD be if this rate is selected
            # Total = Cart Total + Tax + Shipping
            rate_total = summary['total'] + tax_amount + rate['amount']
            
            response_data['rates'].append({
                'id': rate['id'],
                'label': rate['label'],
                'detail': rate['detail'],
                'amount': f"{rate['amount']:.2f}",
                'new_total': f"{rate_total:.2f}" 
            })
            
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_POST
def checkout_update_total(request):
    """
    API called when Shipping Method is selected.
    Updates the Stripe PaymentIntent amount.
    """
    try:
        data = json.loads(request.body)
        payment_intent_id = data.get('payment_intent_id')
        shipping_cost = Decimal(data.get('shipping_cost', '0'))
        tax_cost = Decimal(data.get('tax_cost', '0'))
        
        cart = get_or_create_cart(request)
        summary = get_cart_summary_data(cart)
        
        # Recalculate Final Total
        new_total = summary['total'] + shipping_cost + tax_cost
        new_total_cents = int(new_total * 100)
        
        # Update Stripe
        stripe.PaymentIntent.modify(
            payment_intent_id,
            amount=new_total_cents
        )
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

def create_checkout_session(request):
    """
    Creates a Stripe Checkout session. 
    NOW SUPPORTS: Pre-calculated shipping.
    """
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        return redirect('cart:cart_detail')

    # Parse request body for address data if provided (from JS)
    shipping_amount = 0
    address_data = {}
    
    if request.method == 'POST':
        try:
            body = json.loads(request.body)
            address_data = body.get('address', {})
            
            # Calculate dynamic shipping if address is present
            if address_data:
                shipping_amount = calculate_cart_shipping(cart, address_data)
        except json.JSONDecodeError:
            pass

    # Get summary data and the validated coupon from the cart
    summary_data = get_cart_summary_data(cart)
    coupon = summary_data.get('coupon')

    # If coupon provides free shipping, override calculated shipping
    if coupon and coupon.free_shipping:
        shipping_amount = Decimal('0.00')

    try: # This try now wraps the entire order creation and Stripe session
        with transaction.atomic():
            # 1. Create a pending Order
            user = request.user if request.user.is_authenticated else None
            guest_order_token = None
            if not user:
                guest_order_token = str(uuid.uuid4())

            order = Order.objects.create(
                user=user,
                email=user.email if user else None, # Will be updated by webhook if guest
                total_paid=0.0, # Will be updated by webhook
                shipping_data=address_data,
                status=Order.STATUS_PENDING,
                guest_order_token=guest_order_token,
                coupon=coupon, # Assign the coupon relation
                coupon_code=coupon.code if coupon else None, # Snapshot the code
                discount_amount=summary_data.get('discount_amount', Decimal('0.00')) # Snapshot the amount
            )

            # 2. Create OrderItems from CartItems
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    variant=item.variant,
                    price=item.variant.price,
                    quantity=item.quantity
                )

            # Create line items for Stripe, but we will use a coupon object for the final price
            line_items = []
            for item in cart.items.all():
                line_items.append({
                    'price_data': {
                        'currency': 'gbp',
                        'product_data': {
                            'name': item.variant.product.name,
                            'description': item.variant.name,
                            'images': [request.build_absolute_uri(item.variant.get_image_url())],
                        },
                        'unit_amount': int(item.variant.price * 100),
                    },
                    'quantity': item.quantity,
                })

            # Add Shipping Line Item if applicable
            if shipping_amount > 0:
                line_items.append({
                    'price_data': {
                        'currency': 'gbp',
                        'product_data': {
                            'name': 'Shipping & Handling',
                            'description': 'Standard Shipping',
                        },
                        'unit_amount': int(shipping_amount * 100),
                    },
                    'quantity': 1,
                })

            session_params = {
                'ui_mode': 'embedded',
                'payment_method_types': ['card'],
                'line_items': line_items,
                'mode': 'payment',
                'return_url': request.build_absolute_uri(reverse('payments:payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
                'metadata': {
                    'product_type': 'ecommerce_cart',
                    'order_id': order.id,
                    'user_id': request.user.id if request.user.is_authenticated else None,
                    'guest_order_token': guest_order_token if guest_order_token else '',
                    'shipping_address_json': json.dumps(address_data) if address_data else '',
                    'cart_id': cart.id, # Pass cart_id for later cleanup
                    'coupon_code': coupon.code if coupon else '', # Pass coupon code for webhook logic
                }
            }

            # Apply coupon as a discount in Stripe
            if coupon and summary_data['discount_amount'] > 0:
                stripe_coupon = stripe.Coupon.create(
                    amount_off=int(summary_data['discount_amount'] * 100),
                    currency="gbp",
                    duration="once",
                    name=f"Discount Code: {coupon.code}"
                )
                session_params['discounts'] = [{'coupon': stripe_coupon.id}]

            if not address_data:
                 session_params['shipping_address_collection'] = {
                    'allowed_countries': ['US', 'CA', 'GB', 'AU', 'DE', 'FR', 'ES', 'IT', 'NL'],
                }

            checkout_session = stripe.checkout.Session.create(**session_params)
            return JsonResponse({'clientSecret': checkout_session.client_secret})
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# NEW VIEW for calculating shipping via AJAX/HTMX
@csrf_exempt
def calculate_shipping_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            address = data.get('address')
            cart = get_or_create_cart(request)
            
            cost = calculate_cart_shipping(cart, address)
            return JsonResponse({'shipping_cost': float(cost)})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'POST required'}, status=405)

def payment_success(request):
    """
    Handles the successful payment redirect from Stripe.
    Supports both CHECKOUT SESSIONS (Coaching) and PAYMENT INTENTS (Retail).
    """
    # Stripe automatically adds 'payment_intent' to the URL for Elements
    payment_intent_id = request.GET.get('payment_intent')
    # Your Coaching flow sends 'session_id'
    session_id = request.GET.get('session_id')
    
    cart = get_or_create_cart(request)
    context = {
        'summary': get_cart_summary_data(cart),
        'title': "Payment Successful!",
        'message': "Thank you for your payment.",
        'hero_image': 'images/Success_banner.webp',
    }

    try:
        # --- SCENARIO A: Retail (Stripe Elements / PaymentIntent) ---
        if payment_intent_id:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if intent.status == 'succeeded':
                context['title'] = "Order Confirmed!"
                context['message'] = "Thank you for your purchase. We have received your order and are processing it now."
                
                # OPTIONAL: Clear cart immediately for better UX (in case webhook is slow)
                if intent.metadata.get('cart_id') == str(cart.id):
                    cart.items.all().delete()
                    cart.coupon = None
                    cart.save()
                    # Refresh summary since cart is empty
                    context['summary'] = get_cart_summary_data(cart)
            else:
                context['title'] = "Payment Processing"
                context['message'] = "Your payment is processing. We will update you via email once completed."

        # --- SCENARIO B: Coaching (Checkout Session) ---
        elif session_id:
            session = stripe.checkout.Session.retrieve(session_id)
            metadata = session.metadata
            product_type = metadata.get('product_type')

            if product_type == 'coaching_offering':
                context['title'] = "Enrollment Successful!"
                
                # Fetch details for display
                offering_id = metadata.get('offering_id')
                if offering_id:
                    offering = get_object_or_404(Offering, pk=offering_id)
                    context['offering'] = offering
                    # Use the actual amount paid from the session
                    amount_paid = session.amount_total / 100
                    context['order_summary'] = {'name': offering.name, 'price': amount_paid}

                # Fetch Coach details
                coach_id = metadata.get('coach_id')
                if coach_id:
                    coach = get_object_or_404(CoachProfile, pk=coach_id)
                    context['coach'] = coach
                    context['message'] = f"You have been assigned to {coach.user.get_full_name()}. Check your dashboard to book your first session."

        else:
            # Fallback for direct access without params
            return redirect('accounts:account_profile')
        
        return render(request, 'payments/success.html', context)

    except stripe.InvalidRequestError:
        return HttpResponse("Invalid or expired payment session.", status=400)
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error in payment_success view: {e}", exc_info=True)
        return HttpResponse("An error occurred while confirming your payment.", status=500)

def order_detail_guest(request, guest_order_token):
    """Displays a guest's order details using a secure token."""
    order = get_object_or_404(Order, guest_order_token=guest_order_token)
    return render(request, 'payments/order_detail.html', {'order': order})

def payment_cancel(request):
    return render(request, 'payments/cancel.html')


@csrf_exempt
@transaction.atomic
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse("Invalid payload", status=400)
    except stripe.SignatureVerificationError:
        return HttpResponse("Invalid signature", status=400)

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        metadata = session.get('metadata', {})
        product_type = metadata.get('product_type')
        checkout_session_id = session.id

        # --- IDEMPOTENCY CHECK ---
        # Check if a CoachingOrder or Order has already been successfully processed for this session
        if Order.objects.filter(stripe_checkout_id=checkout_session_id).exists() or \
           CoachingOrder.objects.filter(stripe_checkout_id=checkout_session_id).exists():
            print(f"Webhook for session {checkout_session_id} already processed. Skipping.")
            return HttpResponse(status=200)
        
        # --- E-COMMERCE CART HANDLING ---
        if product_type == 'ecommerce_cart':
            try:
                handle_ecommerce_checkout(session, request)
            except Exception as e:
                logger.error(f"FATAL ERROR in E-commerce Webhook processing: {e}", exc_info=True)
                return HttpResponse("Webhook processing error", status=500)

        # --- NEW E-COMMERCE FLOW (PaymentIntent) ---
        elif event['type'] == 'payment_intent.succeeded':
            intent = event['data']['object']
            # Only process if it's an ecommerce cart intent (check metadata)
            if intent.get('metadata', {}).get('product_type') == 'ecommerce_cart':
                handle_payment_intent_checkout(intent, request)
                return HttpResponse(status=200)

        # --- COACHING HANDLING (Keep existing) ---
        elif product_type == 'coaching_offering':
            try:
                handle_coaching_enrollment(session)
            except Exception as e:
                logger.error(f"FATAL ERROR in Coaching Webhook processing: {e}. Metadata: {metadata}")
                return HttpResponse("Webhook processing error", status=500)

    return HttpResponse(status=200)


@login_required
@require_POST
def create_coaching_checkout_session_view(request, offering_id):
    """
    Handles the creation of a Stripe embedded checkout session for a coaching offering.
    Supports COUPONS and DYNAMIC PRICING.
    """
    offering = get_object_or_404(Offering, pk=offering_id) 

    # 1. Parse Request Data (Handle JSON body)
    try:
        data = json.loads(request.body)
        coupon_code = data.get('coupon_code', '').strip()
    except json.JSONDecodeError:
        # Fallback for standard form posts
        coupon_code = request.POST.get('coupon_code', '').strip()

    # 2. Coupon Logic & Price Calculation
    final_price = offering.price
    discount_amount = Decimal('0.00')
    
    if coupon_code:
        try:
            coupon = Coupon.objects.get(code__iexact=coupon_code)
            # Validate using your existing logic (passing user and cart_value)
            is_valid, msg = coupon.is_valid(user=request.user, cart_value=offering.price)
            
            if is_valid:
                # Calculate discount specifically for this offering
                discount_amount = calculate_discount(coupon, offering=offering)
                final_price = max(offering.price - discount_amount, Decimal('0.00'))
            else:
                return JsonResponse({"error": f"Invalid Coupon: {msg}"}, status=400)
        except Coupon.DoesNotExist:
            return JsonResponse({"error": "Coupon code not found."}, status=400)

    # 3. Coach Assignment (Round Robin / Load Balancing)
    # Only pick coaches who are active and accepting new clients
    available_coaches = CoachProfile.objects.filter(
        offerings=offering, 
        user__is_active=True,
        is_available_for_new_clients=True
    )

    if not available_coaches.exists():
        return JsonResponse({"error": "No coach currently available for this offering."}, status=400)

    # Assign coach with fewest active enrollments for this specific offering
    coach = available_coaches.annotate(
        active_enrollment_count=models.Count(
            'client_enrollments', 
            filter=models.Q(client_enrollments__offering=offering, client_enrollments__is_active=True)
        )
    ).order_by('active_enrollment_count').first()

    if not coach:
        return JsonResponse({"error": "Error: No assignable coach found."}, status=400)

    # 4. Create Stripe Session
    try:
        # Calculate amount in cents/pence
        unit_amount = int(final_price * 100)
        if unit_amount < 50: unit_amount = 50 # Stripe minimum charge

        checkout_session = stripe.checkout.Session.create(
            ui_mode='embedded',
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'gbp',
                    'unit_amount': unit_amount, # <--- DYNAMIC PRICE
                    'product_data': {
                        'name': f"Coaching: {offering.name}"
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            return_url=request.build_absolute_uri(reverse('payments:payment_success')) + '?session_id={CHECKOUT_SESSION_ID}',
            metadata={
                'product_type': 'coaching_offering', 
                'offering_id': str(offering.id),
                'user_id': str(request.user.id),
                'coach_id': str(coach.id),
                'cart_id': str(get_or_create_cart(request).id),
                'coupon_code': coupon_code, # Pass for webhook processing
                'discount_amount': str(discount_amount)
            },
        )
        
        return JsonResponse({
            'clientSecret': checkout_session.client_secret,
            'new_price': f"{final_price:.2f}" # Send new price to frontend for UI update
        })
    except stripe.error.StripeError as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def order_detail(request, order_id):
    """
    Displays order details for a logged-in user.
    Ensures the user can only see their own orders.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/order_detail.html', {'order': order})

# NEW: My Earnings View
class MyEarningsView(ListView):
    model = CoachingOrder
    template_name = 'payments/my_earnings.html'
    context_object_name = 'earnings_records'
    paginate_by = 10

    def get_template_names(self):
        # Return partial template for HTMX requests (keeping user in dashboard)
        if self.request.headers.get('HX-Request'):
            return ['payments/partials/my_earnings_content.html']
        return [self.template_name]

    def get_queryset(self):
        user = self.request.user
        queryset = CoachingOrder.objects.none()

        # Is user a coach?
        if hasattr(user, 'coach_profile'):
            queryset = queryset | CoachingOrder.objects.filter(enrollment__coach=user.coach_profile).annotate(
                earning_type=Value('Coach Fee', output_field=CharField()),
                user_share=F('amount_coach')
            )
        
        # Is user a dreamer/referrer?
        if hasattr(user, 'dreamer_profile'):
            queryset = queryset | CoachingOrder.objects.filter(referrer=user.dreamer_profile).annotate(
                earning_type=Value('Referral Fee', output_field=CharField()),
                user_share=F('amount_referrer')
            )
        
        # Filter out records with 0 share for this user
        queryset = queryset.filter(user_share__gt=0)

        # Apply status filter if present
        status_filter = self.request.GET.get('status')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(payout_status=status_filter)

        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Calculate Totals
        total_unpaid = Decimal('0.00')
        total_unpaid_coach = Decimal('0.00')
        total_unpaid_referrer = Decimal('0.00')

        if hasattr(user, 'coach_profile'):
            coach_unpaid = CoachingOrder.objects.filter(
                enrollment__coach=user.coach_profile, 
                payout_status='unpaid'
            ).aggregate(total=models.Sum('amount_coach'))['total'] or 0
            total_unpaid_coach = Decimal(coach_unpaid)

        if hasattr(user, 'dreamer_profile'):
            ref_unpaid = CoachingOrder.objects.filter(
                referrer=user.dreamer_profile, 
                payout_status='unpaid'
            ).aggregate(total=models.Sum('amount_referrer'))['total'] or 0
            total_unpaid_referrer = Decimal(ref_unpaid)

        context['total_unpaid_combined'] = total_unpaid_coach + total_unpaid_referrer
        context['total_unpaid_coach'] = total_unpaid_coach
        context['total_unpaid_referrer'] = total_unpaid_referrer
        
        context['is_coach_profile'] = hasattr(user, 'coach_profile')
        context['is_dreamer_profile'] = hasattr(user, 'dreamer_profile')
        context['selected_status'] = self.request.GET.get('status', 'all')
        context['payout_statuses'] = CoachingOrder._meta.get_field('payout_status').choices
        
        # Required for the sidebar highlighting
        context['active_tab'] = 'earnings' 
        context['has_earnings_profile'] = context['is_coach_profile'] or context['is_dreamer_profile']

        return context