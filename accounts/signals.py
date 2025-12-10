from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
import uuid
import logging
import stripe

from payments.models import Coupon
from core.email_utils import send_transactional_email

# Set the Stripe API key from settings
stripe.api_key = settings.STRIPE_SECRET_KEY

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


@receiver(post_save, sender=User)
def create_or_update_stripe_customer(sender, instance, created, **kwargs):
    """
    Creates or updates a customer in Stripe when a User is saved.
    """
    # Exit if Stripe is not configured to avoid errors in development/testing
    if not settings.STRIPE_SECRET_KEY:
        return

    user = instance

    try:
        if created and not user.stripe_customer_id:
            # New user: Create a Stripe customer
            customer = stripe.Customer.create(
                email=user.email,
                name=user.get_full_name(),
                metadata={'user_id': user.id, 'username': user.username}
            )
            user.stripe_customer_id = customer.id
            # Use update_fields to avoid re-triggering this signal
            user.save(update_fields=['stripe_customer_id'])
            logger.info(f"Created Stripe customer {customer.id} for new user {user.email}")

        elif not created and user.stripe_customer_id:
            # Existing user with a Stripe ID: Update their details in Stripe
            stripe.Customer.modify(user.stripe_customer_id, email=user.email, name=user.get_full_name())
            logger.info(f"Updated Stripe customer {user.stripe_customer_id} for user {user.email}")
    except Exception as e:
        logger.error(f"Stripe API error for user {user.email}: {e}", exc_info=True)