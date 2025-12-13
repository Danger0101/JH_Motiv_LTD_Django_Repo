from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=300) 
def send_transactional_email_task(self, recipient_email, subject, template_name, context):
    """
    Celery task: Sends a multipart (HTML and plain text) transactional email.
    
    This function contains the actual blocking call to the SMTP server.
    """
    try:
        # --- FIX STARTS HERE: REHYDRATE DJANGO OBJECTS ---
        from django.apps import apps
        
        # Pull required IDs from the context
        booking_id = context.get('booking_id')
        user_id = context.get('user_id')
        coupon_id = context.get('coupon_id')
        coach_id = context.get('coach_id')
        client_id = context.get('client_id')
        offer_id = context.get('offer_id')
        
        # Fetch the actual Django objects for template rendering
        if booking_id:
            try:
                SessionBooking = apps.get_model('coaching_booking', 'SessionBooking')
                # Replaces the SessionBooking object in context
                booking_obj = SessionBooking.objects.get(pk=booking_id)
                context['session'] = booking_obj
                context['booking'] = booking_obj
            except Exception as e:
                logger.warning(f"Booking ID {booking_id} not found for email task: {e}")
        
        if user_id:
            try:
                User = apps.get_model('accounts', 'User')
                # Replaces the User object in context
                context['user'] = User.objects.get(pk=user_id) 
            except Exception as e:
                 logger.warning(f"User ID {user_id} not found for email task: {e}")

        if coupon_id:
            try:
                Coupon = apps.get_model('payments', 'Coupon')
                context['coupon'] = Coupon.objects.get(pk=coupon_id)
            except Exception as e:
                logger.warning(f"Coupon ID {coupon_id} not found for email task: {e}")

        if coach_id:
            try:
                CoachProfile = apps.get_model('accounts', 'CoachProfile')
                context['coach'] = CoachProfile.objects.get(pk=coach_id)
            except Exception as e:
                logger.warning(f"Coach ID {coach_id} not found for email task: {e}")

        if client_id:
            try:
                User = apps.get_model('accounts', 'User')
                context['client'] = User.objects.get(pk=client_id)
            except Exception as e:
                logger.warning(f"Client ID {client_id} not found for email task: {e}")

        if offer_id:
            try:
                OneSessionFreeOffer = apps.get_model('coaching_booking', 'OneSessionFreeOffer')
                context['offer'] = OneSessionFreeOffer.objects.get(pk=offer_id)
            except Exception as e:
                logger.warning(f"OneSessionFreeOffer ID {offer_id} not found for email task: {e}")
        # --- END FIX ---

        # Add the site name to the context for branding
        context['site_name'] = 'JH Motiv LTD'
        
        # Render the HTML content from the template
        html_content = render_to_string(template_name, context)
        
        # Create a plain text version by stripping HTML tags
        text_content = strip_tags(html_content)
        
        # Create the email message
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        
        # Attach the HTML version
        email.attach_alternative(html_content, "text/html")
        
        # Send the email. fail_silently=False ensures exceptions are raised 
        # for Celery to catch and retry.
        email.send(fail_silently=False) 
        
        logger.info(f"Successfully sent email to {recipient_email} with subject: {subject}")
        return True

    except Exception as exc:
        logger.error(f"Attempt {self.request.retries + 1} failed for email to {recipient_email}. Error: {exc}", exc_info=True)
        # Instruct Celery to retry the task (up to max_retries)
        raise self.retry(exc=exc)