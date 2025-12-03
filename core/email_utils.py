from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_transactional_email(recipient_email, subject, template_name, context):
    """
    Sends a multipart (HTML and plain text) transactional email.

    Args:
        recipient_email (str): The email address of the recipient.
        subject (str): The subject of the email.
        template_name (str): The path to the HTML email template.
        context (dict): A dictionary of context data to render the template.
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
        
        # Send the email
        email.send()
        
        logger.info(f"Successfully sent email to {recipient_email} with subject: {subject}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email} with subject: {subject}. Error: {e}", exc_info=True)
        return False
