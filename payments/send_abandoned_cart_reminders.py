import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from cart.models import Cart
from payments.models import Coupon
from core.email_utils import send_transactional_email
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Finds abandoned carts and sends a win-back email with a unique coupon.'

    def handle(self, *args, **options):
        now = timezone.now()
        # Carts updated between 2 and 24 hours ago, not yet submitted, and not yet reminded.
        abandoned_carts = Cart.objects.filter(
            updated_at__range=(now - timedelta(hours=24), now - timedelta(hours=2)),
            status='open',
            abandoned_cart_sent=False,
            user__isnull=False, # Only send to logged-in users with an email
            items__isnull=False # Ensure cart is not empty
        ).select_related('user').distinct()

        self.stdout.write(self.style.SUCCESS(f"Found {abandoned_carts.count()} abandoned carts to process."))

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
                cart_url = reverse('cart:cart_detail') # Assuming you have this URL
                
                # send_transactional_email(
                #     recipient_email=user.email,
                #     subject="Did you forget something?",
                #     template_name='emails/abandoned_cart_reminder.html',
                #     context={
                #         'user': user,
                #         'coupon': win_back_coupon,
                #         'cart_url': cart_url,
                #     }
                # )

                # 3. Mark the cart so we don't send another email
                cart.abandoned_cart_sent = True
                cart.save()

                self.stdout.write(f"Sent win-back email to {user.email} with coupon {code}.")

            except Exception as e:
                logger.error(f"Failed to process abandoned cart {cart.id} for user {user.email}. Error: {e}")

        self.stdout.write(self.style.SUCCESS("Abandoned cart processing complete."))