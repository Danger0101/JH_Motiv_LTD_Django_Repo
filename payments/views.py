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

from cart.utils import get_or_create_cart, get_cart_summary_data
from cart.models import Cart
# NEW/UPDATED IMPORTS
from coaching_booking.models import ClientOfferingEnrollment 
from coaching_core.models import Offering
from accounts.models import CoachProfile
from .models import Order, OrderItem, CoachingOrder
from products.models import Product, Variant
from products.printful_service import PrintfulService
from django.utils import timezone

# Custom imports for email sending
from core.email_utils import send_transactional_email


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
            shipping_address_collection={
                'allowed_countries': ['US', 'CA', 'GB', 'AU', 'DE', 'FR', 'ES', 'IT', 'NL'],
            },
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
        
        if product_type == 'ecommerce_cart':
            cart_id = metadata.get('cart_id')
            if cart_id:
                try:
                    cart = Cart.objects.get(id=cart_id, status='open')
                    
                    # 1. Create Local Order
                    order = Order.objects.create(
                        user_id=metadata.get('user_id'),
                        email=session.get('customer_details', {}).get('email'),
                        total_paid=session.amount_total / 100,
                    )

                    printful_items = []
                    for item in cart.items.all():
                        OrderItem.objects.create(
                            order=order,
                            variant=item.variant,
                            price=item.variant.price,
                            quantity=item.quantity,
                        )
                        # Collect Printful items
                        if item.variant.printful_variant_id:
                            printful_items.append({
                                "variant_id": item.variant.printful_variant_id,
                                "quantity": item.quantity,
                            })
                    
                    # Consolidate Cart
                    cart.status = 'submitted'
                    cart.save()

                    # 2. Handle Printful Fulfillment (Auto vs Manual)
                    if printful_items:
                        auto_fulfill = getattr(settings, 'PRINTFUL_AUTO_FULFILLMENT', False)
                        
                        shipping_details = session.get('shipping_details')
                        address = shipping_details['address'] if shipping_details else {}
                        
                        # Verify Address Data for Printful
                        recipient = {
                            "name": shipping_details.get('name'),
                            "address1": address.get('line1'),
                            "address2": address.get('line2', ''),
                            "city": address.get('city'),
                            "state_code": address.get('state'),  # Stripe 'state' usually maps to region code
                            "country_code": address.get('country'),
                            "zip": address.get('postal_code'),
                            "email": order.email
                        }

                        if auto_fulfill:
                            # AUTOMATIC: Send to Printful immediately
                            printful_service = PrintfulService()
                            print(f"Auto-processing Printful Order for Order #{order.id}")
                            
                            response = printful_service.create_order(recipient, printful_items)
                            
                            if 'result' in response and response['result'].get('id'):
                                order.printful_order_id = response['result']['id']
                                order.printful_order_status = response['result']['status']
                                order.save()
                            else:
                                error_msg = response.get('error', 'Unknown Error')
                                print(f"Printful Auto-Fulfillment Failed: {error_msg}")
                                # Mark as failed so staff can retry manually
                                order.printful_order_status = 'failed_auto_sync'
                                order.save()
                        else:
                            # MANUAL: Mark as pending approval
                            print(f"Manual Mode: Order #{order.id} queued for approval.")
                            order.printful_order_status = 'pending_approval'
                            order.save()

                    # Send Emails (keep existing email logic)
                    try:
                        customer_email = session.get('customer_details', {}).get('email')
                        if not customer_email:
                             raise ValueError("Customer email not found in Stripe session.")

                        user = order.user
                        if user:
                            dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
                        else:
                            # For guests, generate a link to their specific order
                            dashboard_url = request.build_absolute_uri(
                                reverse('payments:order_detail_guest', args=[order.guest_order_token])
                            )

                        email_context = {
                            'order': order,
                            'user': user, # This can be None for guests
                            'dashboard_url': dashboard_url,
                        }

                        send_transactional_email(
                            recipient_email=customer_email,
                            subject=f"Your JH Motiv LTD Order #{order.id} is Confirmed",
                            template_name='emails/order_confirmation.html',
                            context=email_context
                        )
                        print(f"SUCCESS: Order confirmation email sent to {customer_email} for order {order.id}")

                        # Send Payment Receipt Email
                        send_transactional_email(
                            recipient_email=customer_email,
                            subject=f"Your Payment Receipt for Order #{order.id}",
                            template_name='emails/payment_receipt.html',
                            context=email_context
                        )
                        print(f"SUCCESS: Payment receipt email sent to {customer_email} for order {order.id}")

                    except Exception as email_error:
                        print(f"CRITICAL: Order {order.id} created but failed to send email. Error: {email_error}")

                except Exception as e:
                    print(f"Error processing e-commerce order: {e}")
                    return HttpResponse("Error processing order", status=500)
    
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

@login_required
def order_detail(request, order_id):
    """
    Displays order details for a logged-in user.
    Ensures the user can only see their own orders.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'payments/order_detail.html', {'order': order})
