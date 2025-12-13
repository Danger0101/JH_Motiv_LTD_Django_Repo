from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.urls import reverse
from cart.models import Cart
from payments.models import Coupon
from core.email_utils import send_transactional_email
import uuid
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_abandoned_cart_reminders_task(hours_ago=24):
    """
    Finds abandoned carts and sends a win-back email with a unique coupon.
    """
    now = timezone.now()
    # Carts updated between 'hours_ago' and 2 hours ago (buffer), not yet submitted, and not yet reminded.
    start_window = now - timedelta(hours=hours_ago)
    end_window = now - timedelta(hours=2)

    abandoned_carts = Cart.objects.filter(
        updated_at__range=(start_window, end_window),
        status='open',
        abandoned_cart_sent=False,
        user__isnull=False, # Only send to logged-in users with an email
        items__isnull=False # Ensure cart is not empty
    ).select_related('user').distinct()

    logger.info(f"Found {abandoned_carts.count()} abandoned carts to process.")

    for cart in abandoned_carts:
        user = cart.user
        if not user.email:
            continue

        # 1. Create a unique, time-limited coupon for this user
        code = f"COMEBACK-{str(uuid.uuid4())[:5].upper()}"
        valid_until = now + timedelta(hours=48)

        try:
            win_back_coupon = Coupon.objects.create(
                code=code,
                coupon_type='discount',
                discount_type='percent',
                discount_value=5, # 5% off
                usage_limit=1,
                user_specific=user,
                valid_from=now,
                valid_to=valid_until,
                active=True
            )

            # 2. Send the email
            # Construct absolute URL for the cart
            cart_url = f"{settings.SITE_URL}{reverse('cart:cart_detail')}"
            
            send_transactional_email(
                recipient_email=user.email,
                subject="Did you forget something?",
                template_name='emails/abandoned_cart_reminder.html',
                context={
                    'user': user,
                    'coupon': win_back_coupon,
                    'cart_url': cart_url,
                }
            )

            # 3. Mark the cart so we don't send another email
            cart.abandoned_cart_sent = True
            cart.save()

            logger.info(f"Sent win-back email to {user.email} with coupon {code}.")

        except Exception as e:
            logger.error(f"Failed to process abandoned cart {cart.id} for user {user.email}. Error: {e}")
            
    return f"Processed {abandoned_carts.count()} abandoned carts."