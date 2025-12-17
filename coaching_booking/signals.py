from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from .models import SessionBooking
from coaching_core.models import Workshop
# Assuming gcal.utils is the correct import path
from .tasks import send_booking_confirmation_email, sync_google_calendar_push, sync_google_calendar_update, sync_google_calendar_delete, sync_workshop_calendar_push
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

@receiver(post_save, sender=Workshop)
def handle_workshop_gcal(sender, instance, created, **kwargs):
    """
    Signal handler to create/update Google Calendar event for a Workshop.
    """
    workshop = instance
    
    # Trigger sync to create event and generate meeting link
    # We use the same task for create/update for simplicity in this context
    transaction.on_commit(
        lambda: sync_workshop_calendar_push.delay(workshop.id)
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

    elif not created:
        # Existing Booking Updated
        if booking.gcal_event_id:
            # Has ID -> Update existing event
            transaction.on_commit(lambda: sync_google_calendar_update.delay(booking.id))
        else:
            # FIX: No ID exists (sync failed previously?) -> Try Pushing as New
            logger.info(f"Booking {booking.id} updated but has no GCal ID. Attempting push.")
            transaction.on_commit(lambda: sync_google_calendar_push.delay(booking.id))

@receiver(post_delete, sender=SessionBooking)
def handle_session_deletion_gcal(sender, instance, **kwargs):
    """
    Signal handler to delete the Google Calendar event when a booking is deleted or cancelled.
    """
    booking = instance
    
    # Prevent infinite loops: If we are only saving the GCal ID (done by the task itself),
    # do not trigger another sync.
    update_fields = kwargs.get('update_fields')
    if update_fields and 'gcal_event_id' in update_fields and len(update_fields) == 1:
        return
    
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