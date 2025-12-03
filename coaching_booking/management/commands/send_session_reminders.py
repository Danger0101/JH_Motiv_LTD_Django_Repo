import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from datetime import timedelta

from coaching_booking.models import SessionBooking
from core.email_utils import send_transactional_email

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sends reminder emails for sessions occurring in the next 24-25 hours.'

    def handle(self, *args, **options):
        """
        The main logic for the management command.
        """
        now = timezone.now()
        reminder_start_time = now + timedelta(hours=24)
        reminder_end_time = now + timedelta(hours=25)

        # Find sessions that are scheduled to start between 24 and 25 hours from now
        # and have not had a reminder sent yet.
        upcoming_sessions = SessionBooking.objects.filter(
            start_datetime__gte=reminder_start_time,
            start_datetime__lt=reminder_end_time,
            reminder_sent=False,
            status='CONFIRMED'
        ).select_related('client', 'coach__user', 'enrollment__offering')

        self.stdout.write(f"Found {upcoming_sessions.count()} sessions to send reminders for.")
        
        sent_count = 0
        for session in upcoming_sessions:
            try:
                # --- Send reminder to Client ---
                client_dashboard_url = f"https://{settings.ALLOWED_HOSTS[2]}{reverse('accounts:account_profile')}"
                client_context = {
                    'user': session.client,
                    'session': session,
                    'dashboard_url': client_dashboard_url,
                }
                send_transactional_email(
                    recipient_email=session.client.email,
                    subject="Reminder: Your Coaching Session is Tomorrow",
                    template_name='emails/session_reminder.html',
                    context=client_context
                )

                # --- Send reminder to Coach ---
                coach_dashboard_url = f"https://{settings.ALLOWED_HOSTS[2]}{reverse('accounts:account_profile')}"
                coach_context = {
                    'user': session.coach.user,
                    'session': session,
                    'dashboard_url': coach_dashboard_url,
                }
                send_transactional_email(
                    recipient_email=session.coach.user.email,
                    subject=f"Reminder: Session with {session.client.get_full_name()} Tomorrow",
                    template_name='emails/session_reminder.html', # Can reuse the same template
                    context=coach_context
                )

                # Mark the session as having had a reminder sent
                session.reminder_sent = True
                session.save(update_fields=['reminder_sent'])
                sent_count += 1

            except Exception as e:
                logger.error(f"Failed to send reminder for session {session.id}. Error: {e}", exc_info=True)

        self.stdout.write(self.style.SUCCESS(f"Successfully sent {sent_count} reminder(s)."))
