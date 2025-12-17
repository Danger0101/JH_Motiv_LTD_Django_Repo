from celery import shared_task, current_app
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.urls import reverse
from core.email_utils import send_transactional_email
from .models import SessionBooking
from .utils import generate_ics
from .integrations.google import GoogleCalendarService
from coaching_core.models import CoachProfile
from coaching_core.models import Workshop
from datetime import timedelta
from django.utils import timezone
import requests
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def send_booking_confirmation_email(self, booking_id):
    try:
        booking = SessionBooking.objects.get(id=booking_id)
        
        # 1. Determine Context (Workshop vs 1-on-1)
        subject = "Booking Confirmed: "
        if booking.workshop:
            subject += booking.workshop.title
            template_name = "emails/booking_workshop_confirmed.html"
            event_details = f"{booking.workshop.title} with {booking.workshop.coach.user.get_full_name()}"
        else:
            subject += f"1-on-1 with {booking.coach.user.get_full_name()}"
            # Re-using existing template or creating a generic one if needed. 
            # Based on previous context, you had 'emails/booking_confirmation.html'
            template_name = "emails/booking_confirmation.html" 
            event_details = f"Session with {booking.coach.user.get_full_name()}"

        # 2. Render Content
        # Determine recipient name and email
        recipient_name = booking.guest_name or (booking.client.first_name if booking.client else "Guest")
        recipient_email = booking.guest_email or (booking.client.email if booking.client else None)

        if not recipient_email:
            logger.error(f"No email found for booking {booking.id}")
            return

        context = {
            'name': recipient_name,
            'session': booking, # Passing full object for template flexibility
            'date': booking.start_datetime, 
            'details': event_details,
            'dashboard_url': f"{settings.SITE_URL}/accounts/profile/", 
        }
        
        html_content = render_to_string(template_name, context)
        text_content = strip_tags(html_content)

        # 3. Construct Email
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient_email]
        )
        msg.attach_alternative(html_content, "text/html")
        
        # 4. Generate and Attach ICS
        ics_data, ics_filename = generate_ics(booking)
        msg.attach(ics_filename, ics_data, 'text/calendar')

        msg.send()
        
        logger.info(f"Confirmation email sent to {recipient_email} for booking {booking.id}")

    except SessionBooking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found during email task.")
    except Exception as e:
        logger.error(f"Failed to send email for booking {booking_id}: {e}")
        # Exponential backoff retry
        self.retry(exc=e, countdown=60)

@shared_task
def release_expired_holds():
    """
    Runs every 10 minutes.
    Deletes bookings that are PENDING_PAYMENT for > 15 minutes.
    """
    threshold = timezone.now() - timedelta(minutes=15)
    
    stale_bookings = SessionBooking.objects.filter(
        status='PENDING_PAYMENT',
        created_at__lt=threshold
    )
    
    count = stale_bookings.count()
    stale_bookings.delete()
    
    return f"Released {count} expired holds."

@shared_task
def sync_google_calendar_push(booking_id):
    try:
        booking = SessionBooking.objects.get(id=booking_id)
        service = GoogleCalendarService(booking.coach)
        gcal_id = service.push_booking(booking)
        
        if gcal_id:
            booking.gcal_event_id = gcal_id
            booking.save(update_fields=['gcal_event_id'])
    except SessionBooking.DoesNotExist:
        pass

@shared_task
def sync_google_calendar_update(booking_id):
    try:
        booking = SessionBooking.objects.get(id=booking_id)
        # Only attempt update if we have an event ID to update
        if booking.gcal_event_id:
            service = GoogleCalendarService(booking.coach)
            service.update_booking(booking)
    except SessionBooking.DoesNotExist:
        pass

@shared_task
def sync_google_calendar_delete(coach_id, gcal_event_id):
    # We pass IDs separately because the Booking object might be deleted already
    try:
        coach = CoachProfile.objects.get(id=coach_id)
        service = GoogleCalendarService(coach)
        service.delete_booking(gcal_event_id)
    except CoachProfile.DoesNotExist:
        pass

@shared_task
def sync_workshop_calendar_push(workshop_id):
    """
    Syncs a Workshop to the Coach's Google Calendar and saves the meeting link.
    """
    try:
        workshop = Workshop.objects.get(id=workshop_id)
        service = GoogleCalendarService(workshop.coach)
        
        # Note: Ensure GoogleCalendarService has a push_workshop method
        # that handles creating an event with conferenceData and returns (event_id, meet_link)
        # If push_workshop is not available, this logic needs to be added to the service.
        result = service.push_workshop(workshop)
        
        if result:
            # Result expected to be dict or tuple with id and link
            # This depends on your Service implementation
            pass 
            
    except Workshop.DoesNotExist:
        pass
    except Exception as e:
        logger.error(f"Failed to sync workshop {workshop_id} to GCal: {e}")

@shared_task
def sync_google_calendar_pull_all():
    """
    Scheduled task (Celery Beat): Runs every 15 mins.
    """
    # Iterate over coaches who have credentials (logic depends on auth implementation)
    for coach in CoachProfile.objects.all():
        try:
            service = GoogleCalendarService(coach)
            service.sync_busy_slots()
        except Exception as e:
            logger.error(f"Failed to sync calendar for coach {coach}: {e}")

@shared_task
def send_upcoming_session_reminders():
    """
    Sends reminder emails for sessions occurring in the next 24-25 hours.
    """
    now = timezone.now()
    reminder_start_time = now + timedelta(hours=24)
    reminder_end_time = now + timedelta(hours=25)

    upcoming_sessions = SessionBooking.objects.filter(
        start_datetime__gte=reminder_start_time,
        start_datetime__lt=reminder_end_time,
        reminder_sent=False,
        status='BOOKED'
    ).select_related('client', 'coach__user', 'enrollment__offering')

    sent_count = 0
    for session in upcoming_sessions:
        try:
            # --- Send reminder to Client ---
            client_dashboard_url = f"{settings.SITE_URL}{reverse('accounts:account_profile')}"
            client_context = {
                'user_id': session.client.pk,
                'booking_id': session.pk,
                'dashboard_url': client_dashboard_url,
            }
            send_transactional_email(
                recipient_email=session.client.email,
                subject="Reminder: Your Coaching Session is Tomorrow",
                template_name='emails/session_reminder.html',
                context=client_context
            )

            # --- Send reminder to Coach ---
            coach_dashboard_url = f"{settings.SITE_URL}{reverse('accounts:account_profile')}"
            coach_context = {
                'user_id': session.coach.user.pk,
                'booking_id': session.pk,
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
            
    return f"Sent {sent_count} session reminders."

@shared_task
def health_check_email_worker():
    # If this doesn't run, we know the worker is dead.
    # Use a service like DeadManSnitch or Cronitor
    # Replace URL with your actual monitoring URL
    # requests.get("https://nosnch.in/YOUR_ID")
    pass

@current_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Run release_expired_holds every 10 minutes (600 seconds)
    sender.add_periodic_task(600.0, release_expired_holds.s(), name='release_expired_holds_every_10_mins')
    
    # Run sync_google_calendar_pull_all every 15 minutes (900 seconds)
    sender.add_periodic_task(900.0, sync_google_calendar_pull_all.s(), name='sync_google_calendar_pull_all_every_15_mins')