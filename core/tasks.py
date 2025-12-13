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
    Celery task to send a multipart (HTML and plain text) transactional email.
    """
    try:
        # 1. Logic is the same as your existing email_utils.py function
        context['site_name'] = 'JH Motiv LTD'
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")
        
        # 2. Use fail_silently=False for Celery task to catch exceptions
        email.send(fail_silently=False) 
        
        logger.info(f"Successfully sent email to {recipient_email} with subject: {subject}")
        return True

    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_email}. Retrying...")
        # 3. Retry the task on failure
        raise self.retry(exc=exc)