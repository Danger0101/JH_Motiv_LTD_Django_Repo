import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse
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
from django.utils import timezone
from django.views.generic import ListView, View
from django.db.models import F, Value, CharField # Import F, Value, and CharField for annotations
from .finance_utils import calculate_coaching_split
from .shipping_utils import calculate_cart_shipping
import logging
import json
import uuid

# Custom imports for email sending
from core.email_utils import send_transactional_email


logger = logging.getLogger(__name__)
User = get_user_model() # Get the user model
stripe.api_key = settings.STRIPE_SECRET_KEY

def checkout_cart_view(request):
    """
    Renders the dedicated Cart Checkout page (Physical products).
    This is where the user enters their address for shipping calculation.
    """
    cart = get_or_create_cart(request)
    if not cart or not cart.items.exists():
        return redirect('cart:cart_detail')
        
    # Get summary data. Re-validation happens inside this function.
    summary = get_cart_summary_data(cart)
    
    return render(request, 'payments/checkout_cart.html', {
        'cart': cart,
        'summary': summary,
        'STRIPE_PUBLISHABLE_KEY': settings.STRIPE_PUBLISHABLE_KEY
    })

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
    except Exception as e:
        print(f"Error creating Stripe checkout session: {e}")
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
    Displays a confirmation message and ensures all required template variables are present.
    """
    session_id = request.GET.get('session_id')
    cart = get_or_create_cart(request)

    # Base context for all paths to prevent KeyErrors in templates.
    context = {
        'summary': get_cart_summary_data(cart), # Cart is now empty, but function is safe
        'order_summary': {},
        'title': "Payment Successful!",
        'message': "Thank you for your payment.",
        'coach': None,
    }

    if not session_id:
        # If no session ID is provided, show a generic success page with dummy data as requested.
        coach_profile = None
        try:
            # Attempt to find the specific coach 'John Hummel'.
            user = User.objects.get(first_name="John", last_name="Hummel", is_coach=True)
            coach_profile = CoachProfile.objects.get(user=user)
        except (User.DoesNotExist, CoachProfile.DoesNotExist, User.MultipleObjectsReturned):
            # Fallback to the first available coach if not found.
            coach_profile = CoachProfile.objects.first()

        context.update({
            'title': 'Enrollment Confirmed',
            'message': 'Thank you for your coaching enrollment! You will receive a confirmation email shortly.',
            'order_summary': {'name': 'Executive Scale Mastermind', 'price': '€1999'},
            'coach': coach_profile,
        })
        return render(request, 'payments/success.html', context)

    try:
        session = stripe.checkout.Session.retrieve(session_id)
        metadata = session.metadata
        product_type = metadata.get('product_type')

        if product_type == 'coaching_offering':
            context['title'] = "Enrollment Successful!"
            offering_id = metadata.get('offering_id')
            offering = get_object_or_404(Offering, pk=offering_id) if offering_id else None
            
            if offering:
                context['offering'] = offering
                context['order_summary'] = {'name': offering.name, 'price': f"€{offering.price}"}

            coach_id = metadata.get('coach_id')
            if coach_id:
                coach = get_object_or_404(CoachProfile, pk=coach_id)
                context['coach'] = coach
                context['message'] = (
                    f"You have been successfully enrolled and assigned to coach {coach.user.get_full_name()}. "
                    f"You can now visit your dashboard to book your first session."
                )
            else:
                context['message'] = "Thank you for enrolling. You will receive a confirmation email with details on how to book your sessions."

        elif product_type == 'ecommerce_cart':
            context['message'] = "Thank you for your purchase. Your order is being processed and you will receive a confirmation email shortly."
        
        return render(request, 'payments/success.html', context)

    except stripe.InvalidRequestError:
        return HttpResponse("Invalid or expired payment session.", status=400)
    except Exception as e:
        print(f"Error in payment_success view: {e}")
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
            order_id = metadata.get('order_id')
            if not order_id:
                print("FATAL ERROR in E-commerce Webhook: order_id not found in metadata.")
                return HttpResponse("Missing order_id in metadata", status=400)
            
            try:
                order = Order.objects.select_for_update().get(id=order_id)

                # Prevent reprocessing
                if order.status != Order.STATUS_PENDING:
                    print(f"Webhook for order {order_id} already processed. Status: {order.status}")
                    return HttpResponse(status=200)
                
                # Update Order status and total_paid
                order.status = Order.STATUS_PAID
                order.total_paid = session.amount_total / 100
                order.stripe_checkout_id = checkout_session_id # Record the session ID

                # Clear coupon from cart after successful payment (moved from payment_success)
                if order.coupon and metadata.get('cart_id'):
                    Cart.objects.filter(id=metadata.get('cart_id')).update(coupon=None)
                # Update email if it was a guest user and email is now available from Stripe
                if not order.user and session.get('customer_details', {}).get('email'):
                    # If it's a guest, try to find a user by this email to check for self-referral
                    try:
                        potential_user = User.objects.get(email=session.get('customer_details', {}).get('email'))
                        # If a coupon was used, check if this user is the referrer
                        coupon_code = metadata.get('coupon_code')
                        if coupon_code:
                            try:
                                coupon = Coupon.objects.get(code=coupon_code)
                                if coupon.affiliate_dreamer and coupon.affiliate_dreamer.user == potential_user:
                                    # This is a self-referral by a guest who has an account
                                    # We can log this, but the main logic is in finance_utils
                                    logger.info(f"Potential self-referral detected for guest order {order.id} with email {potential_user.email}")
                            except Coupon.DoesNotExist:
                                pass
                    except User.DoesNotExist:
                        pass # It's a true guest
                    order.email = session.get('customer_details', {}).get('email')

                # Update shipping_data if it wasn't present before or if Stripe has more complete data
                if not order.shipping_data:
                    shipping_json = metadata.get('shipping_address_json')
                    shipping_data_from_metadata = json.loads(shipping_json) if shipping_json else {}
                    
                    if shipping_data_from_metadata:
                        order.shipping_data = shipping_data_from_metadata
                    else:
                        # Fallback to Stripe's data if our metadata is empty
                        shipping_details = session.get('shipping_details') or {}
                        address = shipping_details.get('address') or {}
                        order.shipping_data = {
                            'name': shipping_details.get('name'),
                            'address1': address.get('line1'),
                            'address2': address.get('line2'),
                            'city': address.get('city'),
                            'state_code': address.get('state'),
                            'country_code': address.get('country'),
                            'zip': address.get('postal_code'),
                        }
                order.save()

                # If a coupon was used, create a usage record
                if order.coupon: # Check if coupon was applied to the order
                    # --- HANDLE RACE CONDITION ---
                    try:
                        # Lock the coupon row until this transaction is complete
                        coupon = order.coupon.__class__.objects.select_for_update().get(id=order.coupon.id)
                        
                        # Re-check usage limit inside the lock
                        if coupon.usage_limit is not None and coupon.usages.count() >= coupon.usage_limit:
                            logger.warning(f"Coupon {coupon.code} was oversold on Order {order.id}. Usage limit was exceeded.")
                        
                        from .models import CouponUsage
                        CouponUsage.objects.create(
                            coupon=coupon,
                            order=order,
                            user=order.user,
                            email=order.email
                        )
                    except order.coupon.DoesNotExist:
                        logger.error(f"Could not log usage for a coupon on Order {order.id} because the coupon was deleted mid-transaction.")

                printful_items = []

                # Process Items & Deduct Stock (using OrderItems now)
                for item in order.items.all(): # order.items is OrderItem related_name
                    # A. Handle Printful Items
                    if item.variant.printful_variant_id:
                        printful_items.append({
                            "variant_id": item.variant.printful_variant_id,
                            "quantity": item.quantity,
                        })
                    
                    # B. Handle Self-Fulfilled Stock Deduction
                    if item.variant.product.product_type == 'physical' and item.variant.stock_pool:
                        try:
                            # Lock the pool row to prevent race conditions
                            pool = StockPool.objects.select_for_update().get(id=item.variant.stock_pool.id)
                            
                            if pool.available_stock < 9000: 
                                if pool.available_stock >= item.quantity:
                                    pool.available_stock -= item.quantity
                                    pool.save()
                                    print(f"Stock deducted: {item.quantity} from {pool.name}")
                                else:
                                    print(f"CRITICAL: Oversold {pool.name}. Had {pool.available_stock}, sold {item.quantity}.")
                                    pool.available_stock = 0
                                    pool.save()
                        except StockPool.DoesNotExist:
                            print(f"Error: StockPool not found for variant {item.variant.id}")

                # Clear the user's cart now that the order is complete
                cart_id_from_metadata = metadata.get('cart_id')
                if cart_id_from_metadata:
                    try:
                        # We don't delete, we just clear the items.
                        # This preserves the cart for logged-in users.
                        original_cart = Cart.objects.get(id=cart_id_from_metadata)
                        original_cart.items.all().delete()
                        print(f"Cart {cart_id_from_metadata} cleared after order {order_id} completion.")
                    except Cart.DoesNotExist:
                        print(f"WARNING: Original cart {cart_id_from_metadata} not found during webhook processing.")
                else:
                    print(f"WARNING: No cart_id found in metadata for order {order_id}. Cannot clear original cart.")


                # Handle Printful Fulfillment
                if printful_items:
                    auto_fulfill = getattr(settings, 'PRINTFUL_AUTO_FULFILLMENT', False)
                    
                    if auto_fulfill:
                        printful_service = PrintfulService()
                        recipient = {
                            "name": order.shipping_data.get('name'),
                            "address1": order.shipping_data.get('address1'),
                            "address2": order.shipping_data.get('address2', ''),
                            "city": order.shipping_data.get('city'),
                            "state_code": order.shipping_data.get('state_code'),
                            "country_code": order.shipping_data.get('country_code'),
                            "zip": order.shipping_data.get('zip'),
                            "email": order.email
                        }
                        
                        response = printful_service.create_order(recipient, printful_items)
                        
                        if 'result' in response and response['result'].get('id'):
                            order.printful_order_id = response['result']['id']
                            order.printful_order_status = response['result']['status']
                            order.save()
                        else:
                            print(f"Printful Auto-Sync Failed: {response}")
                            order.printful_order_status = 'failed_auto_sync'
                            order.save()
                    else:
                        order.printful_order_status = 'pending_approval'
                        order.save()
                        print(f"Order #{order.id} queued for manual Printful approval.")

                # Send Confirmation Emails
                try:
                    customer_email = order.email # Use email from order, which is now guaranteed to be set
                    if not customer_email:
                         raise ValueError("Customer email not found on order after webhook processing.")

                    user = order.user
                    if user:
                        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
                    else:
                        dashboard_url = request.build_absolute_uri(
                            reverse('payments:order_detail_guest', args=[order.guest_order_token])
                        )

                    email_context = {
                        'order': order,
                        'user': user,
                        'dashboard_url': dashboard_url,
                    }

                    send_transactional_email(
                        recipient_email=customer_email,
                        subject=f"Your JH Motiv LTD Order #{order.id} is Confirmed",
                        template_name='emails/order_confirmation.html',
                        context=email_context
                    )
                    print(f"SUCCESS: Order confirmation email sent to {customer_email} for order {order.id}")

                    send_transactional_email(
                        recipient_email=customer_email,
                        subject=f"Your Payment Receipt for Order #{order.id}",
                        template_name='emails/payment_receipt.html',
                        context=email_context
                    )
                    print(f"SUCCESS: Payment receipt email sent to {customer_email} for order {order.id}")

                except Exception as email_error:
                    print(f"CRITICAL: Order {order.id} updated but failed to send email. Error: {email_error}")

            except Order.DoesNotExist:
                print(f"FATAL ERROR in E-commerce Webhook: Order matching ID {order_id} does not exist.")
                return HttpResponse("Order not found", status=400)
            except Exception as e:
                print(f"FATAL ERROR in E-commerce Webhook processing Order {order_id}: {e}")
                return HttpResponse("Webhook processing error", status=500)

        # --- COACHING HANDLING (Keep existing) ---
        elif product_type == 'coaching_offering':
            user_id = metadata.get('user_id')
            offering_id = metadata.get('offering_id')
            coach_id = metadata.get('coach_id')
            total_paid_amount = Decimal(session.amount_total) / Decimal('100')

            try:
                user = User.objects.get(id=user_id)
                offering = Offering.objects.get(id=offering_id)
                coach = CoachProfile.objects.get(id=coach_id)

                # Create the enrollment record
                enrollment = ClientOfferingEnrollment.objects.create(
                    client=user,
                    offering=offering,
                    coach=coach,
                    remaining_sessions=offering.total_number_of_sessions,
                    is_active=True
                )

                # Check for Coupon/Referrer in metadata
                coupon_code = session.metadata.get('coupon_code')
                referrer = None
                coupon = None # Initialize coupon to None
                
                if coupon_code:
                    try:
                        coupon = Coupon.objects.get(code=coupon_code)
                        referrer = coupon.affiliate_dreamer # From our previous design
                    except Coupon.DoesNotExist:
                        pass

                # Create the CoachingOrder
                coaching_order = CoachingOrder.objects.create(
                    enrollment=enrollment,
                    referrer=referrer,
                    amount_gross=total_paid_amount,
                    stripe_checkout_id=checkout_session_id # Record the session ID
                )

                # If a coupon was used, create a usage record for coaching orders
                if coupon: # 'coupon' variable from above referrer check
                    Coupon.objects.get(code=coupon_code).usages.create(user=user, email=user.email, order=None) # No direct Order model for coaching
                
                # RUN THE SPLIT CALCULATION
                splits = calculate_coaching_split(total_paid_amount, enrollment.offering, referrer, client=user)
                
                # Save the splits
                coaching_order.amount_coach = splits['coach']
                coaching_order.amount_referrer = splits['referrer']
                coaching_order.amount_company = splits['company']
                coaching_order.save()

            except (User.DoesNotExist, Offering.DoesNotExist, CoachProfile.DoesNotExist) as e:
                logger.error(f"FATAL ERROR in Coaching Webhook: Could not find object. {e}. Metadata: {metadata}")
                return HttpResponse("Webhook processing error: object not found", status=400)
            except Exception as e:
                logger.error(f"FATAL ERROR in Coaching Webhook processing: {e}. Metadata: {metadata}")
                return HttpResponse("Webhook processing error", status=500)

    return HttpResponse(status=200)


def create_coaching_checkout_session_view(request, offering_id):
    """
    Handles the creation of a Stripe embedded checkout session for a coaching offering.
    This is intended to be called via a POST request from the checkout page.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"error": "User not authenticated"}, status=403)

    offering = get_object_or_404(Offering, pk=offering_id) 

    if request.method == 'POST':
        available_coaches = CoachProfile.objects.filter(
            offerings=offering, 
            user__is_active=True,
            is_available_for_new_clients=True
        )

        if not available_coaches.exists():
            return JsonResponse({"error": "No coach currently available for this offering."}, status=400)

        coach = available_coaches.annotate(
            active_enrollment_count=models.Count(
                'client_enrollments', 
                filter=models.Q(client_enrollments__offering=offering, client_enrollments__is_active=True)
            )
        ).order_by('active_enrollment_count').first()

        if not coach:
            return JsonResponse({"error": "Error: No assignable coach found."}, status=400)

        try:
            checkout_session = stripe.checkout.Session.create(
                ui_mode='embedded',
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'gbp',
                        'unit_amount': int(offering.price * 100),
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
                    'cart_id': get_or_create_cart(request).id, # Add cart_id for potential clearing
                    'coupon_code': request.POST.get('coupon_code', ''), # Pass coupon from the form
                },
            )
            
            return JsonResponse({'clientSecret': checkout_session.client_secret})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # This view should only handle POST requests for creating the session
    return JsonResponse({'error': 'Invalid request method'}, status=405)

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