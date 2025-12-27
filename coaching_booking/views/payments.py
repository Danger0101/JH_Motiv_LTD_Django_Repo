from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
import stripe
from django.conf import settings
import json

from coaching_core.models import Offering
from ..models import SessionBooking

logger = logging.getLogger(__name__)
stripe.api_key = settings.STRIPE_SECRET_KEY

@login_required
@require_POST
def create_checkout_session(request, offering_id):
    offering = get_object_or_404(Offering, id=offering_id)
    selected_coach_id = request.POST.get('coach_id')
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=request.user.email,
            line_items=[{'price_data': {'currency': 'gbp', 'product_data': {'name': offering.name}, 'unit_amount': int(offering.price * 100)}, 'quantity': 1}],
            mode='payment',
            success_url=request.build_absolute_uri(reverse('accounts:account_profile')),
            cancel_url=request.build_absolute_uri(request.META.get('HTTP_REFERER', '/')),
            metadata={'offering_id': offering.id, 'user_id': request.user.id, 'coach_id': selected_coach_id, 'type': 'offering_enrollment'},
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logger.error(f"Stripe Checkout Error: {e}")
        messages.error(request, "Unable to initiate checkout.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

@login_required
def session_payment_page(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    if booking.status != 'PENDING_PAYMENT':
        messages.info(request, "Session not pending payment.")
        return redirect('accounts:account_profile')

    remaining_seconds = (booking.created_at + timedelta(minutes=15) - timezone.now()).total_seconds()
    if remaining_seconds <= 0:
        messages.error(request, "Hold expired.")
        return redirect('accounts:account_profile')

    checkout_url = None
    if booking.stripe_checkout_session_id:
        try: checkout_url = stripe.checkout.Session.retrieve(booking.stripe_checkout_session_id).url
        except: pass
    
    return render(request, 'coaching_booking/session_payment.html', {'booking': booking, 'checkout_url': checkout_url, 'remaining_seconds': int(remaining_seconds)})

@login_required
def check_payment_status(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if booking.status == 'BOOKED':
        return HttpResponse('<div class="text-center text-green-600 font-bold p-4">Payment Confirmed!</div>', status=200)
    return render(request, 'coaching_booking/partials/spinner.html', {'booking': booking})