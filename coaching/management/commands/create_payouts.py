from django.core.management.base import BaseCommand
from django.utils import timezone
from coaching.models import CoachingSession, CoachPayout, CoachOffering

class Command(BaseCommand):
    help = 'Create payouts for completed sessions'

    def handle(self, *args, **options):
        completed_sessions = CoachingSession.objects.filter(
            status='BOOKED',
            end_time__lt=timezone.now(),
            paid_out=False
        )

        for session in completed_sessions:
            try:
                offering = CoachOffering.objects.get(name=session.service_name, coach=session.coach)
                if offering.rate:
                    CoachPayout.objects.create(
                        coach=session.coach,
                        amount=offering.rate
                    )
                    session.paid_out = True
                    session.save()
                    self.stdout.write(self.style.SUCCESS(f'Successfully created payout for session {session.id}'))
                else:
                    self.stdout.write(self.style.WARNING(f'No rate set for offering {offering.name} of session {session.id}'))
            except CoachOffering.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Could not find offering for session {session.id}'))
