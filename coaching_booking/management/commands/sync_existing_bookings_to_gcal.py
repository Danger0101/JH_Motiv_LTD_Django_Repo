from django.core.management.base import BaseCommand
from django.utils import timezone
from coaching_booking.models import SessionBooking
from coaching_booking.tasks import sync_google_calendar_push

class Command(BaseCommand):
    help = 'Manually syncs all future, active bookings to Google Calendar for connected coaches.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without actually doing it.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()
        
        # Find bookings that:
        # 1. Are active (Booked/Rescheduled)
        # 2. Are in the future
        # 3. Have NOT been synced to GCal yet (gcal_event_id is null)
        # 4. Belong to a coach who has GCal credentials
        bookings_to_sync = SessionBooking.objects.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now,
            gcal_event_id__isnull=True,
            coach__user__google_calendar_credentials__isnull=False
        ).exclude(
            coach__user__google_calendar_credentials=''
        )

        count = bookings_to_sync.count()
        
        if count == 0:
            self.stdout.write(self.style.WARNING("No eligible bookings found to sync."))
            return

        self.stdout.write(f"Found {count} bookings eligible for sync.")

        if dry_run:
            for booking in bookings_to_sync:
                self.stdout.write(f"[DRY RUN] Would sync Booking #{booking.id} for {booking.coach.user.get_full_name()} at {booking.start_datetime}")
            return

        for booking in bookings_to_sync:
            self.stdout.write(f"Queuing sync for Booking #{booking.id} (Coach: {booking.coach.user.get_full_name()})")
            # Use .delay() to offload to Celery worker if available, preventing timeout on large batches
            sync_google_calendar_push.delay(booking.id)

        self.stdout.write(self.style.SUCCESS(f"Successfully queued {count} sync tasks."))