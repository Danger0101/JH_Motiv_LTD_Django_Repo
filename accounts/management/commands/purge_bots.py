from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Deletes unverified users older than 24 hours'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=24)
        # Assuming you use allauth's EmailAddress model to check verification
        from allauth.account.models import EmailAddress
        
        unverified_emails = EmailAddress.objects.filter(verified=False, user__date_joined__lt=cutoff)
        count = unverified_emails.count()
        
        users_to_delete = unverified_emails.values_list('user', flat=True)
        User.objects.filter(pk__in=list(users_to_delete)).delete()
            
        self.stdout.write(f"Successfully deleted {count} unverified bot accounts.")
