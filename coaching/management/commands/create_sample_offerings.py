from django.core.management.base import BaseCommand
from coaching.models import CoachOffering

class Command(BaseCommand):
    help = 'Creates sample coaching offerings for the platform.'

    def handle(self, *args, **kwargs):
        offerings = [
            {
                'name': 'Momentum Catalyst Session',
                'slug': 'taster-session',
                'description': 'A 30-minute high-impact session to experience coaching and gain immediate clarity.',
                'duration_minutes': 30,
                'price': 0.00,
                'credits_granted': 1,
                'duration_months': 12,
                'is_active': True,
            },
            {
                'name': 'Clarity Call',
                'slug': 'clarity-call',
                'description': 'A 60-minute deep-dive session to untangle a specific challenge and create an actionable plan.',
                'duration_minutes': 60,
                'price': 99.00,
                'credits_granted': 1,
                'duration_months': 3,
                'is_active': True,
            },
            {
                'name': 'Momentum Builder Program',
                'slug': 'momentum-builder',
                'description': 'A 3-month program with 4 sessions designed to build and sustain momentum towards your biggest goals.',
                'duration_minutes': 60,
                'price': 349.00,
                'credits_granted': 4,
                'duration_months': 3,
                'is_active': True,
            },
        ]

        for offering_data in offerings:
            obj, created = CoachOffering.objects.update_or_create(slug=offering_data['slug'], defaults=offering_data)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Successfully created offering: '{obj.name}'"))
            else:
                self.stdout.write(self.style.WARNING(f"Offering '{obj.name}' already exists, updated instead."))