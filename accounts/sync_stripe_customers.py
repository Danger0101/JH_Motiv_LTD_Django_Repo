import stripe
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Syncs existing users with Stripe, creating Stripe customers for those who do not have one.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit the number of users to sync in one run.',
            default=None
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Count users to be synced without actually performing the sync.',
        )

    def handle(self, *args, **options):
        if not settings.STRIPE_SECRET_KEY:
            raise CommandError("Stripe secret key is not configured in settings.")

        stripe.api_key = settings.STRIPE_SECRET_KEY
        
        limit = options['limit']
        dry_run = options['dry_run']

        # Find users who don't have a Stripe customer ID yet.
        users_to_sync = User.objects.filter(stripe_customer_id__isnull=True)

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Found {users_to_sync.count()} users to sync with Stripe."))
            return

        if limit:
            users_to_sync = users_to_sync[:limit]

        if not users_to_sync.exists():
            self.stdout.write(self.style.SUCCESS("All users are already synced with Stripe."))
            return

        self.stdout.write(f"Found {users_to_sync.count()} users to sync...")

        synced_count = 0
        failed_count = 0

        for user in users_to_sync:
            try:
                customer = stripe.Customer.create(
                    email=user.email,
                    name=user.get_full_name(),
                    metadata={'user_id': user.id, 'username': user.username}
                )
                user.stripe_customer_id = customer.id
                user.save(update_fields=['stripe_customer_id'])
                self.stdout.write(self.style.SUCCESS(f"Successfully created Stripe customer {customer.id} for user {user.email}"))
                synced_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to create Stripe customer for user {user.email}: {e}"))
                failed_count += 1
        
        self.stdout.write("\n--- Sync Complete ---")
        self.stdout.write(self.style.SUCCESS(f"Synced: {synced_count} | Failed: {failed_count}"))