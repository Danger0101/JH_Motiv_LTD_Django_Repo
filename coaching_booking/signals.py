from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
# Note: Ensure this import path is correct for your SessionBooking model
from .models import SessionBooking 
# Note: Ensure this import path is correct for your gcal utility file
from gcal.utils import create_calendar_event, delete_calendar_event 

import logging
logger = logging.getLogger(__name__)

@receiver(post_save, sender=SessionBooking)
def handle_session_booking_gcal(sender, instance, created, **kwargs):
    """
    Signal handler to create or update a Google Calendar event.
    """
    booking = instance
    
    if booking.status != 'CONFIRMED':
        # Only create/update events for confirmed bookings
        return
    
    if created:
        # New Booking - Create Event
        # NOTE: This function is asynchronous and non-blocking in a real production environment (e.g., using Celery)
        try:
            create_calendar_event(booking)
            logger.info(f"GCal: Triggered event CREATE for booking {booking.id}")
        except Exception as e:
            logger.error(f"GCal Error on Creation for Booking {booking.id}: {e}")

    elif not created and booking.gcal_event_id:
        # Existing Booking Updated (e.g., Rescheduled) - Update Event
        # NOTE: If time/coach changes, this should trigger an UPDATE function.
        # For now, we log the intent as the utility is simple.
        logger.info(f"GCal: Booking {booking.id} updated. Triggering event UPDATE (if implemented).")
        # In a complete app: update_calendar_event(booking)

@receiver(post_delete, sender=SessionBooking)
def handle_session_deletion_gcal(sender, instance, **kwargs):
    """
    Signal handler to delete the Google Calendar event when a booking is deleted/cancelled.
    """
    booking = instance
    
    if booking.gcal_event_id:
        try:
            delete_calendar_event(booking)
            logger.info(f"GCal: Triggered event DELETE for booking {booking.id}")
        except Exception as e:
            logger.error(f"GCal Error on Deletion for Booking {booking.id}: {e}")