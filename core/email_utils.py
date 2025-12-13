from .tasks import send_transactional_email_task
import logging

logger = logging.getLogger(__name__)

def send_transactional_email(recipient_email, subject, template_name, context):
    """
    Queues a multipart transactional email for asynchronous sending via Celery.
    """
    try:
        # Call .delay() to execute the task asynchronously
        send_transactional_email_task.delay(recipient_email, subject, template_name, context)
        logger.info(f"Queued email to {recipient_email} with subject: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to queue email task for {recipient_email}. Error: {e}", exc_info=True)
        # If queuing fails, you may choose to send synchronously as a fallback 
        # or just log and fail, depending on your error policy.
        return False
