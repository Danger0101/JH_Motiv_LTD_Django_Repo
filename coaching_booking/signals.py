from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SessionBooking 
# Assuming gcal.utils is the correct import path
from .tasks import send_booking_confirmation_email, sync_google_calendar_push
from django.core.cache import cache

import logging
logger = logging.getLogger(__name__)


@receiver(post_save, sender=SessionBooking)
def handle_session_booking_gcal(sender, instance, created, **kwargs):
    """
    Signal handler to create or update a Google Calendar event when a booking is saved.
    """
    booking = instance
    
    # Invalidate Calendar Cache
    if booking.coach:
        version_key = f"coach_calendar_version_{booking.coach.id}"
        cache.incr(version_key)
    
    # Only process confirmed bookings
    if booking.status != 'CONFIRMED':
        return
    
    # Use a thread or Celery task in production for non-blocking API calls
    
    if created:
        # 1. New Booking - Create Event
        transaction.on_commit(lambda: sync_google_calendar_push.delay(booking.id))
            
        # 2. Trigger Async Email Task
        # Use on_commit to ensure DB row exists for the worker
        transaction.on_commit(lambda: send_booking_confirmation_email.delay(booking.id))

    elif not created and booking.gcal_event_id:
        # 2. Existing Booking Updated (e.g., Rescheduled, Time/Coach Change) - Update Event
        # Implement an update function in gcal/utils.py later
        logger.info(f"GCal: Booking {booking.id} updated. Requires UPDATE logic.")
        # try:
        #     update_calendar_event(booking)
        # except Exception as e:
        #     logger.error(f"GCal Error on Update for Booking {booking.id}: {e}", exc_info=True)
        pass 

@receiver(post_delete, sender=SessionBooking)
def handle_session_deletion_gcal(sender, instance, **kwargs):
    """
    Signal handler to delete the Google Calendar event when a booking is deleted or cancelled.
    """
    booking = instance
    
    # Invalidate Calendar Cache
    if booking.coach:
        version_key = f"coach_calendar_version_{booking.coach.id}"
        cache.incr(version_key)
    
    if booking.gcal_event_id:
        # Implement delete logic in GoogleCalendarService if needed, or keep existing if it works
        pass