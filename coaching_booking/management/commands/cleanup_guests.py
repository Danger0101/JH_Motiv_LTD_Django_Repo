from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from accounts.models import User

class Command(BaseCommand):
    help = 'Deletes guest accounts older than 30 days and warns those older than 27 days.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # 1. WARNING EMAILS (27 days old)
        # We look for users created between 27 and 28 days ago to catch them exactly 3 days before expiry
        warn_start = now - timedelta(days=28)
        warn_end = now - timedelta(days=27)
        
        guests_to_warn = User.objects.filter(
            date_joined__gt=warn_start,
            date_joined__lt=warn_end
        ).exclude(
            billing_notes=''
        ).exclude(
            billing_notes__isnull=True
        )
        
        for guest in guests_to_warn:
            token = guest.billing_notes
            # Construct absolute URL
            path = reverse('coaching_booking:guest_access', args=[token])
            access_url = f"{settings.SITE_URL}{path}"
            
            send_mail(
                subject="Action Required: Your Guest Account Expires Soon",
                message=f"Your guest account created on {guest.date_joined.date()} will be deleted in 3 days.\n\n"
                        f"To keep your account and booking history, please activate it here:\n{access_url}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[guest.email],
            )
            self.stdout.write(f"Sent warning to {guest.email}")

        # 2. DELETION (30 days old)
        delete_threshold = now - timedelta(days=30)
        
        guests_to_delete = User.objects.filter(
            date_joined__lt=delete_threshold
        ).exclude(
            billing_notes=''
        ).exclude(
            billing_notes__isnull=True
        )
        
        count = guests_to_delete.count()
        if count > 0:
            guests_to_delete.delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired guest accounts."))
        else:
            self.stdout.write("No expired accounts found.")