from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import uuid
import logging

from payments.models import Coupon
from core.email_utils import send_transactional_email

User = get_user_model()
logger = logging.getLogger(__name__)

@receiver(post_save, sender=User)
def create_welcome_coupon(sender, instance, created, **kwargs):
    """
    When a new user is created, generate a unique, single-use welcome coupon
    and email it to them.
    """
    if created:
        # Generate a unique code like WELCOME-K82L
        code = f"WELCOME-{str(uuid.uuid4())[:4].upper()}"
        valid_until = timezone.now() + timedelta(days=7)

        try:
            welcome_coupon = Coupon.objects.create(
                code=code,
                discount_type='percent',
                discount_value=10,
                usage_limit=1,
                user_specific=instance, # Restrict to this new user
                valid_to=valid_until,
                active=True
            )

            # Send email with the new code
            # (Assumes you have an email template at 'emails/welcome_coupon.html')
            # send_transactional_email(...)
            logger.info(f"Successfully created welcome coupon {code} for new user {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create welcome coupon for user {instance.email}. Error: {e}")