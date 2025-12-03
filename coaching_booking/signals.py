from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import SessionBooking 
# Assuming gcal.utils is the correct import path
from gcal.utils import create_calendar_event, delete_calendar_event 

import logging
logger = logging.getLogger(__name__)


@receiver(post_save, sender=SessionBooking)
def handle_session_booking_gcal(sender, instance, created, **kwargs):
    """
    Signal handler to create or update a Google Calendar event when a booking is saved.
    """
    booking = instance
    
    # Only process confirmed bookings
    if booking.status != 'CONFIRMED':
        return
    
    # Use a thread or Celery task in production for non-blocking API calls
    
    if created:
        # 1. New Booking - Create Event
        try:
            create_calendar_event(booking)
            logger.info(f"GCal: Triggered event CREATE for booking {booking.id}")
        except Exception as e:
            logger.error(f"GCal Error on Creation for Booking {booking.id}: {e}", exc_info=True)

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
    
    if booking.gcal_event_id:
        try:
            delete_calendar_event(booking)
            logger.info(f"GCal: Triggered event DELETE for booking {booking.id}")
        except Exception as e:
            logger.error(f"GCal Error on Deletion for Booking {booking.id}: {e}", exc_info=True)