import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from .models import Order

from coaching_core.models import Offering

stripe.api_key = settings.STRIPE_SECRET_KEY

def create_checkout_session(request, offering_id):
    """
    Creates a Stripe Checkout session for the selected coaching offering.
    """
    offering = get_object_or_404(Offering, pk=offering_id)
    
    # Build the success URL, which will eventually point to a confirmation page
    # For now, let's redirect to a simple success page.
    success_url = request.build_absolute_uri(reverse('payments:payment_success'))
    cancel_url = request.build_absolute_uri(reverse('payments:payment_cancel'))

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'gbp',
                        'product_data': {
                            'name': offering.name,
                            'description': offering.description,
                        },
                        'unit_amount': int(offering.price * 100),  # Stripe expects amount in cents
                    },
                    'quantity': 1,
                }
            ],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                'offering_id': offering.id,
                'user_id': request.user.id if request.user.is_authenticated else None,
            }
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        # Log the error and return a user-friendly error page
        print(f"Error creating Stripe checkout session: {e}")
        # In a real app, you'd render an error template
        return HttpResponse("Error creating checkout session.", status=500)

def payment_success(request):
    """
    Handles the successful payment redirect from Stripe.
    This is where you would create the ClientOfferingEnrollment.
    """
    # For now, just a simple success message.
    # In a real implementation, you'd use the webhook to confirm the payment
    # and the session ID from the URL to display order details.
    return render(request, 'payments/success.html')

def order_detail_guest(request, guest_order_token):
    """Displays a guest's order details using a secure token."""
    order = get_object_or_404(Order, guest_order_token=guest_order_token)
    return render(request, 'payments/order_detail.html', {'order': order})

def payment_cancel(request):
    return render(request, 'payments/cancel.html')

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event based on its type
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        # Fulfill the purchase...
        # You can get the program_id from the session metadata if you pass it during creation
        print(f"Checkout session completed: {session.id}")

    return HttpResponse(status=200)

