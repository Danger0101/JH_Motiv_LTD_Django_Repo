import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from .models import SessionBooking
import logging

logger = logging.getLogger(__name__)

@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    # HANDLE SUCCESSFUL PAYMENT
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        # Check if this is OUR booking
        if session.get('metadata', {}).get('type') == 'coaching_booking':
            booking_id = session['metadata']['booking_id']
            
            try:
                booking = SessionBooking.objects.get(id=booking_id)
                
                # Idempotency Check: Don't confirm twice
                if not booking.is_paid:
                    booking.is_paid = True
                    booking.status = 'BOOKED' # Maps to CONFIRMED in your logic
                    booking.amount_paid = session['amount_total']
                    booking.save() 
                    
            except SessionBooking.DoesNotExist:
                return HttpResponse(status=404)

    return HttpResponse(status=200)