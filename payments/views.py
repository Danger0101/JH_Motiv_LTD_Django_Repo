import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db import transaction, models # ADDED: models for coach query
from django.contrib.auth import get_user_model # ADDED: Better way to get User model

from cart.utils import get_or_create_cart, get_cart_summary_data
from cart.models import Cart
# NEW/UPDATED IMPORTS
from coaching_booking.models import ClientOfferingEnrollment 
from coaching_core.models import Offering
from accounts.models import CoachProfile
from .models import Order, OrderItem
from products.models import Product, Variant

User = get_user_model() # Get the user model
stripe.api_key = settings.STRIPE_SECRET_KEY

def create_checkout_session(request):
    """
    Creates a Stripe Checkout session for an embedded UI based on the user's current cart.
    FIX: The 'return_url' no longer contains the literal session ID placeholder.
    """
    cart = get_or_create_cart(request)
    if not cart.items.exists():
        return redirect('cart:cart_detail')

    line_items = []
    for item in cart.items.all():
        line_items.append({
            'price_data': {
                'currency': 'gbp',
                'product_data': {
                    'name': item.variant.product.name,
                    'description': item.variant.name,
                },
                'unit_amount': int(item.variant.price * 100),
            },
            'quantity': item.quantity,
        })

    try:
        checkout_session = stripe.checkout.Session.create(
            ui_mode='embedded',
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            # --- FIX APPLIED ---
            # Stripe will automatically append ?session_id={CHECKOUT_SESSION_ID}
            return_url=request.build_absolute_uri(reverse('payments:payment_success')),
            # --- END FIX ---
            metadata={
                'product_type': 'ecommerce_cart',
                'cart_id': cart.id,
                'user_id': request.user.id if request.user.is_authenticated else None,
            }
        )
        return JsonResponse({'clientSecret': checkout_session.client_secret})
    except Exception as e:
        print(f"Error creating Stripe checkout session: {e}")
        return JsonResponse({'error': str(e)}, status=500)

def payment_success(request):
    """
    Handles the successful payment redirect from Stripe.
    Displays a confirmation message and ensures all required template variables are present.
    """
    session_id = request.GET.get('session_id')
    cart = get_or_create_cart(request)
    
    # Base context for all paths to prevent KeyErrors in templates.
    context = {
        'summary': get_cart_summary_data(cart),
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
@transaction.atomic # Ensure all database operations succeed or fail together
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    # 1. Verify Webhook Signature
    try:
        # NOTE: settings.STRIPE_WEBHOOK_SECRET must be configured
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse("Invalid payload", status=400)
    except stripe.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse("Invalid signature", status=400)

    # 2. Handle 'checkout.session.completed' Event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Only proceed if payment was actually successful
        if session.get('payment_status') != 'paid':
            print(f"Skipping session {session.id}: Not paid.")
            return HttpResponse(status=200)

        # Retrieve the CRITICAL routing metadata
        metadata = session.get('metadata', {})
        # --- FIX: Be explicit about 'product_type' ---
        # Do not provide a default. If it's missing, it's a critical error.
        product_type = metadata.get('product_type')
        
        if not product_type:
            print(f"FATAL ERROR: Webhook for session {session.id} is missing 'product_type' in metadata.")
            # Return a 500 to force Stripe to retry. This gives you time to investigate.
            return HttpResponse("Webhook Error: Missing product_type in metadata.", status=500)

        print(f"Processing session {session.id} for product_type: '{product_type}'")

        # --- A. COACHING ENROLLMENT LOGIC (Priority) ---
        if product_type == 'coaching_offering':
            try:
                user_id = metadata.get('user_id')
                offering_id = metadata.get('offering_id')
                coach_id = metadata.get('coach_id')

                if not all([user_id, offering_id, coach_id]):
                    raise ValueError("Missing required metadata for coaching enrollment (user_id, offering_id, or coach_id).")

                # Fetch related objects
                user = get_object_or_404(User, pk=user_id)
                offering = get_object_or_404(Offering, pk=offering_id)
                coach_profile = get_object_or_404(CoachProfile, pk=coach_id)

                # Check for existing enrollment to prevent webhook retries causing duplicates
                if ClientOfferingEnrollment.objects.filter(client=user, offering=offering, is_active=True).exists():
                    print(f"Duplicate enrollment skipped for user {user.id} in offering {offering.id}.")
                    return HttpResponse(status=200)

                # Create the Client Offering Enrollment (New Client Creation)
                ClientOfferingEnrollment.objects.create(
                    client=user,
                    offering=offering,
                    coach=coach_profile
                )
                
                print(f"SUCCESS: Client Enrollment created for {user.email} in {offering.name}")
                
            except Exception as e:
                print(f"FATAL ERROR in Coaching Enrollment: {e}")
                return HttpResponse("Coaching Enrollment failed.", status=500)

        # --- B. E-COMMERCE ORDER LOGIC (Fallback/General Cart) ---
        elif product_type == 'ecommerce_cart':
            cart_id = metadata.get('cart_id')
            
            if cart_id:
                try:
                    # Retrieve the cart that initiated the payment
                    cart = Cart.objects.get(id=cart_id, status='open')
                    
                    # 1. Create the Order
                    order = Order.objects.create(
                        user_id=metadata.get('user_id'),
                        total_paid=session.amount_total / 100,
                        # NOTE: Ensure you add address/guest info here if needed!
                    )

                    # 2. Create Order items from cart items
                    for item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            variant=item.variant,
                            price=item.variant.price, # Use the price at time of payment
                            quantity=item.quantity,
                        )
                    
                    # 3. Mark the cart as submitted (consumed)
                    cart.status = 'submitted'
                    cart.save()

                    print(f"SUCCESS: E-commerce Order {order.id} created from cart {cart.id}")

                except Cart.DoesNotExist:
                    print(f"E-commerce cart ID {cart_id} not found or already submitted. Skipping.")
                except Exception as e:
                    print(f"FATAL ERROR in E-commerce Order: {e}")
                    return HttpResponse("E-commerce Order failed.", status=500)
        
        else:
            print(f"Unknown product_type: {product_type}. Skipping.")


    # 3. Acknowledge Receipt
    # Always return a 200 status code to Stripe unless a fatal, non-recoverable error occurred
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
                },
            )
            
            return JsonResponse({'clientSecret': checkout_session.client_secret})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    # This view should only handle POST requests for creating the session
    return JsonResponse({'error': 'Invalid request method'}, status=405)