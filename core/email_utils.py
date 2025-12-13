from .tasks import send_transactional_email_task # <-- NEW IMPORT
# Removed unnecessary imports: EmailMultiAlternatives, render_to_string, strip_tags
import logging

logger = logging.getLogger(__name__)

def send_transactional_email(recipient_email, subject, template_name, context):
    """
    Queues a multipart transactional email for asynchronous sending via Celery.

    Args:
        recipient_email (str): The email address of the recipient.
        subject (str): The subject of the email.
        template_name (str): The path to the HTML email template.
        context (dict): A dictionary of context data to render the template.
    """
    try:
        # Call the task asynchronously using .delay()
        send_transactional_email_task.delay(recipient_email, subject, template_name, context)
        
        logger.info(f"Queued email task for {recipient_email} with subject: {subject}")
        return True

    except Exception as e:
        # This catch block now only handles errors in queuing the task to Celery, 
        # not the actual SMTP transmission error.
        logger.error(f"Failed to queue email task for {recipient_email} with subject: {subject}. Error: {e}", exc_info=True)
        return False
