from celery import shared_task
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.utils import timezone
import logging
try:
    import weasyprint
except (OSError, ImportError):
    weasyprint = None

from django.core import signing
from django.urls import reverse
from .models import Newsletter, NewsletterSubscriber

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
        order_id = context.get('order_id')
        user_id = context.get('user_id')
        coupon_id = context.get('coupon_id')
        coach_id = context.get('coach_id')
        client_id = context.get('client_id')
        offer_id = context.get('offer_id')
        newsletter_id = context.get('newsletter_id')
        
        # Fetch the actual Django objects for template rendering
        if order_id:
            try:
                Order = apps.get_model('payments', 'Order')
                context['order'] = Order.objects.get(pk=order_id)
            except Exception as e:
                logger.warning(f"Order ID {order_id} not found for email task: {e}")

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

        if newsletter_id:
            try:
                Newsletter = apps.get_model('core', 'Newsletter')
                context['newsletter'] = Newsletter.objects.get(pk=newsletter_id)
            except Exception as e:
                logger.warning(f"Newsletter ID {newsletter_id} not found for email task: {e}")
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

@shared_task
def send_welcome_email_with_pdf_task(recipient_email, base_url):
    """
    Generates the Blueprint PDF and sends it as an attachment in a welcome email.
    """
    if weasyprint is None:
        logger.warning("PDF Generation skipped: WeasyPrint libraries not found on this machine.")
        return

    try:
        # 1. Generate PDF
        html_string = render_to_string('pdfs/game_master_blueprint.html')
        pdf_bytes = weasyprint.HTML(string=html_string, base_url=base_url).write_pdf()

        # 2. Prepare Email
        subject = "Welcome to the Guild - Your Blueprint is Inside"
        
        # Generate unsubscribe link
        token = signing.dumps(recipient_email, salt='newsletter-unsubscribe')
        unsubscribe_path = reverse('core:unsubscribe_newsletter', args=[token])
        unsubscribe_url = f"{base_url.rstrip('/')}{unsubscribe_path}"

        body_html = "<p>Welcome to the JH Motiv Guild! We are glad to have you.</p><p>Please find your Game Master's Blueprint attached.</p>"
        
        context = {'body': body_html, 'unsubscribe_url': unsubscribe_url}
        html_content = render_to_string('core/generic_newsletter.html', context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        
        # 3. Attach PDF
        email.attach('Game_Masters_Blueprint.pdf', pdf_bytes, 'application/pdf')
        email.attach_alternative(html_content, "text/html")
        
        # 4. Send
        email.send(fail_silently=False)
        logger.info(f"Sent welcome email with PDF to {recipient_email}")
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {recipient_email}: {e}", exc_info=True)

@shared_task
def send_newsletter_blast_task(newsletter_id):
    """
    Sends a database-backed newsletter to all active subscribers.
    Updates status to 'sent' upon completion.
    """
    try:
        newsletter = Newsletter.objects.get(id=newsletter_id)
        subscribers = NewsletterSubscriber.objects.filter(is_active=True)
        
        # Select Template
        template_path = f"emails/newsletters/layout_{newsletter.template}.html"
        
        success_count = 0
        
        for sub in subscribers:
            # Generate Unique Unsubscribe Link
            # In real production, you might want to sign this token or use the existing signing logic
            token = sub.email 
            unsubscribe_url = f"{settings.SITE_URL}/newsletter/unsubscribe/{token}/"
            
            context = {
                'newsletter': newsletter,
                'subscriber': sub,
                'unsubscribe_url': unsubscribe_url,
                'site_url': settings.SITE_URL,
            }
            
            html_content = render_to_string(template_path, context)
            
            try:
                send_mail(
                    subject=newsletter.subject,
                    message="", # Plain text fallback could be generated here
                    html_message=html_content,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[sub.email],
                    fail_silently=False
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send to {sub.email}: {e}")
                
        # Update status to sent if it was scheduled
        if newsletter.status != 'sent':
            newsletter.status = 'sent'
            newsletter.sent_at = timezone.now()
            newsletter.save()

        return f"Sent {success_count} emails for campaign: {newsletter.subject}"
        
    except Newsletter.DoesNotExist:
        return "Newsletter not found"