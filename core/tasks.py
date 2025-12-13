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