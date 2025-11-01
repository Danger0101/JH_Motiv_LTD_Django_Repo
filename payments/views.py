import stripe
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from .models import Order
from coaching.models import CoachingProgram, UserProgram, SessionCredit

stripe.api_key = settings.STRIPE_SECRET_KEY

def order_detail_guest(request, guest_order_token):
    """Displays a guest's order details using a secure token."""
    order = get_object_or_404(Order, guest_order_token=guest_order_token)
    return render(request, 'payments/order_detail.html', {'order': order})

def create_checkout_session(request, program_id):
    program = get_object_or_404(CoachingProgram, id=program_id)
    if request.method == 'POST':
        try:
            checkout_session = stripe.checkout.Session.create(
                line_items=[
                    {
                        'price_data': {
                            'currency': 'gbp',
                            'product_data': {
                                'name': program.name,
                            },
                            'unit_amount': int(program.price * 100),
                        },
                        'quantity': 1,
                    },
                ],
                mode='payment',
                success_url=request.build_absolute_uri(reverse('payments:payment_success')) + f'?session_id={{CHECKOUT_SESSION_ID}}&program_id={program.id}',
                cancel_url=request.build_absolute_uri(reverse('payments:payment_cancel')),
            )
            return redirect(checkout_session.url, code=303)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return render(request, 'payments/checkout.html', {'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY, 'program': program})

def payment_success(request):
    session_id = request.GET.get('session_id')
    program_id = request.GET.get('program_id')
    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            program = get_object_or_404(CoachingProgram, id=program_id)
            
            # Create UserProgram
            user_program = UserProgram.objects.create(
                user=request.user,
                program=program,
            )
            
            # Create SessionCredits
            for i in range(program.credits_granted):
                SessionCredit.objects.create(
                    user=request.user,
                    user_program=user_program,
                )

            return render(request, 'payments/success.html', {'session': session})
        except stripe.error.StripeError as e:
            return HttpResponse(f"Error retrieving session: {e}", status=400)
    return redirect('/')

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

