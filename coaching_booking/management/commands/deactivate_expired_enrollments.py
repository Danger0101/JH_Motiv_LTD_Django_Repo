from django.core.management.base import BaseCommand
from django.utils import timezone
from coaching_booking.models import ClientOfferingEnrollment

class Command(BaseCommand):
    help = 'Identifies and deactivates enrollments that have passed their expiration date.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Filter for active enrollments that have an expiration date in the past
        expired_enrollments = ClientOfferingEnrollment.objects.filter(
            is_active=True,
            expiration_date__lt=now
        )
        
        count = expired_enrollments.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('No expired enrollments found.'))
            return

        self.stdout.write(f'Found {count} expired enrollments. Deactivating...')

        for enrollment in expired_enrollments:
            # The save() method in ClientOfferingEnrollment now handles the logic
            # to set is_active=False and deactivated_on=now if expired.
            enrollment.save()
            self.stdout.write(f' - Deactivated enrollment {enrollment.id} (Client: {enrollment.client})')
            
        self.stdout.write(self.style.SUCCESS(f'Successfully processed {count} enrollments.'))