# coaching_checkout/views.py
import stripe
import json
import logging
from decimal import Decimal
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View, TemplateView
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction

# Assumed imports for client enrollment
from coaching_core.models import Offering
from coaching_booking.models import ClientOfferingEnrollment
from accounts.models import CoachProfile # Assuming CoachProfile can be imported
from accounts.models import User # Assuming User can be imported

# Initialize Stripe with your secret key
# MAKE SURE THIS IS CONFIGURED IN settings.py
stripe.api_key = settings.STRIPE_SECRET_KEY

# --- 💸 Create Checkout Session View ---

class CreateCoachingCheckoutSessionView(LoginRequiredMixin, View):
    """
    Creates a Stripe Checkout Session for a single coaching offering.
    This replaces the 'OfferEnrollmentStartView' redirect in coaching_booking/views.py.
    """
    def post(self, request, *args, **kwargs):
        # 1. Get the Offering and User
        offering = get_object_or_404(Offering, slug=self.kwargs['slug'])
        user = self.request.user

        # Security Check: Ensure the user is authenticated (LoginRequiredMixin handles most of this)
        # You may add a check to ensure the user doesn't have an active enrollment already

        # 2. Select a Coach (Simplification: Select the first available coach)
        coach_profile = offering.coaches.first()
        if not coach_profile:
            # Handle case where no coach is assigned to the offering
            return JsonResponse({'error': 'No coach available for this offering.'}, status=400)

        try:
            # 3. Create a Stripe Checkout Session
            # Convert price to cents (Stripe expects the amount in the smallest currency unit)
            price_in_cents = int(offering.price * Decimal('100'))
            
            # Metadata to be retrieved in the webhook
            metadata = {
                'offering_id': str(offering.id),
                'offering_name': offering.name,
                'user_id': str(user.id),
                'coach_id': str(coach_profile.id),
            }

            checkout_session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': 'usd', # Use your currency
                        'unit_amount': price_in_cents,
                        'product_data': {
                            'name': f"Coaching: {offering.name}",
                            'description': offering.description[:500],
                        },
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=request.build_absolute_uri(reverse('coaching_checkout:checkout_success')),
                cancel_url=request.build_absolute_uri(reverse('coaching_checkout:checkout_cancel')),
                # Pass necessary data via client_reference_id and metadata
                client_reference_id=str(user.id),
                metadata=metadata,
            )

            # 4. Return the session ID to the frontend to redirect to Stripe
            return JsonResponse({
                'id': checkout_session.id,
                'stripe_publishable_key': settings.STRIPE_PUBLISHABLE_KEY # Should be configured
            })

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# --- ✅ Stripe Webhook Handler ---

logger = logging.getLogger(__name__)

@csrf_exempt
def stripe_webhook_received(request):
    """
    Stripe Webhook handler to confirm payment and create the ClientOfferingEnrollment.
    This is the DEDICATED COACHING PAYMENT CONFIRMATION.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    event = None

    logger.info(f"Webhook payload: {payload}")

    try:
        # Use your actual webhook secret
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload: {e}")
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        logger.error(f"Invalid signature: {e}")
        return HttpResponse(status=400)

    logger.info(f"Event type: {event['type']}")

    # Handle the checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        logger.info(f"Session object: {session}")
        
        # Check if payment was successful
        if session.get('payment_status') == 'paid':
            try:
                # 1. Retrieve data from metadata
                user_id = session.metadata.get('user_id')
                offering_id = session.metadata.get('offering_id')
                coach_id = session.metadata.get('coach_id')
                
                logger.info(f"User ID: {user_id}, Offering ID: {offering_id}, Coach ID: {coach_id}")

                # Check for existing enrollment (avoids double enrollment on webhook retry)
                if ClientOfferingEnrollment.objects.filter(
                    client_id=user_id,
                    offering_id=offering_id
                ).exists():
                    logger.warning(f"User {user_id} already enrolled in offering {offering_id}.")
                    return HttpResponse(status=200) # Already handled, return 200 to Stripe

                # 2. Fetch necessary objects
                user = get_object_or_404(User, id=user_id)
                offering = get_object_or_404(Offering, id=offering_id)
                coach = get_object_or_404(CoachProfile, id=coach_id)

                # 3. Use a transaction for safety
                with transaction.atomic():
                    # 4. Create the ClientOfferingEnrollment (the 'new client' data)
                    logger.info("Creating new client enrollment...")
                    enrollment = ClientOfferingEnrollment.objects.create(
                        client=user,
                        offering=offering,
                        coach=coach,
                        # total_sessions and remaining_sessions are handled by save/signals/defaults
                    )
                    
                    # Log or perform other client-specific actions (e.g., welcome email, etc.)
                    logger.info(f"New client enrolled: {enrollment}")

            except Exception as e:
                # Log the error and consider notifying an admin
                logger.error(f"Error processing coaching enrollment: {e}")
                # Do NOT return a 200 status unless the error is one we can safely ignore (like a duplicate)
                return HttpResponse(status=500) # Indicate failure to Stripe for retry
        
    return HttpResponse(status=200) # Acknowledge receipt of the webhook event

# --- Success/Cancel Views ---

class CheckoutSuccessView(LoginRequiredMixin, TemplateView):
    """Page shown after successful payment. Enrollment is confirmed by webhook."""
    template_name = 'coaching_checkout/success.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message'] = "Your payment was successful and your coaching enrollment is being set up!"
        return context

class CheckoutCancelView(TemplateView):
    """Page shown if the client cancels the Stripe Checkout."""
    template_name = 'coaching_checkout/cancel.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message'] = "Your checkout was canceled. You can try again at any time."
        return context