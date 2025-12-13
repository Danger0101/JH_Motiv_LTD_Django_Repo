from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SessionBooking 
# Assuming gcal.utils is the correct import path
from .tasks import send_booking_confirmation_email, sync_google_calendar_push, sync_google_calendar_update, sync_google_calendar_delete
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
        try:
            cache.incr(version_key)
        except ValueError:
            cache.set(version_key, 1)
    
    # HANDLE CANCELLATIONS
    if booking.status == 'CANCELED' and booking.gcal_event_id:
        transaction.on_commit(
            lambda: sync_google_calendar_delete.delay(booking.coach.id, booking.gcal_event_id)
        )
        return

    # Only process confirmed bookings
    # FIX: Model uses 'BOOKED' and 'RESCHEDULED', not 'CONFIRMED'
    if booking.status not in ['BOOKED', 'RESCHEDULED']:
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
        # Trigger Async Update Task
        transaction.on_commit(lambda: sync_google_calendar_update.delay(booking.id))

@receiver(post_delete, sender=SessionBooking)
def handle_session_deletion_gcal(sender, instance, **kwargs):
    """
    Signal handler to delete the Google Calendar event when a booking is deleted or cancelled.
    """
    booking = instance
    
    # Invalidate Calendar Cache
    if booking.coach:
        version_key = f"coach_calendar_version_{booking.coach.id}"
        try:
            cache.incr(version_key)
        except ValueError:
            cache.set(version_key, 1)
    
    if booking.gcal_event_id and booking.coach:
        # Pass IDs explicitly because 'booking' instance doesn't exist in DB for the task to fetch
        transaction.on_commit(
            lambda: sync_google_calendar_delete.delay(booking.coach.id, booking.gcal_event_id)
        )