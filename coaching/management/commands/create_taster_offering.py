from django.core.management.base import BaseCommand
from coaching.models import CoachOffering
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Creates or updates the standard taster session offering.'

    def handle(self, *args, **options):
        User = get_user_model()
        
        offering, created = CoachOffering.objects.update_or_create(
            slug='taster-session',
            defaults={
                'name': 'Momentum Catalyst Session',
                'description': 'A one-time, 90-minute introductory session to experience coaching.',
                'duration_minutes': 90,
                'price': 0.00,
                'credits_granted': 1,
                'duration_months': 12, # Access to book this is 12 months
                'is_active': True,
                'rate': 0.00, # No payout for a free session
            }
        )

        # Ensure all coaches are associated with the taster offering
        all_coaches = User.objects.filter(is_coach=True)
        offering.coaches.set(all_coaches)
        
        if created:
            self.stdout.write(self.style.SUCCESS('Successfully created the taster session offering.'))
        else:
            self.stdout.write(self.style.SUCCESS('Taster session offering already exists, updated.'))
