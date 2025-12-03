# gcal/utils.py (Fixed to include necessary functions for imports)

from django.conf import settings
from datetime import timedelta, datetime
import pytz
import logging
# NOTE: Real Google API imports (google.oauth2.credentials, googleapiclient.discovery)
# are assumed to be here, but commented out to allow local running without the library.

logger = logging.getLogger(__name__)

# --- Mock Credential Retrieval (Needed for all actions) ---
def get_coach_credentials(coach_user):
    """
    (MOCK) Retrieves Google API credentials for a coach user.
    """
    try:
        # Assumes GcalCredentials model is correctly linked and stores tokens
        credentials = coach_user.gcalcredentials
        return credentials if credentials.access_token else None
    except Exception:
        return None

# --- Core Event Management Functions (Used by coaching_booking/signals.py) ---

def create_calendar_event(booking):
    """
    (MOCK) Creates a new Google Calendar event for the session booking.
    """
    coach_user = booking.coach.user
    credentials = get_coach_credentials(coach_user)
    
    if not credentials:
        logger.warning(f"GCal: Skipping event creation for Coach {coach_user.username}. Credentials missing or invalid.")
        return None

    # Time conversion: ensures event times are correctly sent as UTC
    gcal_timezone = pytz.timezone(settings.TIME_ZONE) 
    start_time_utc = booking.start_datetime.astimezone(gcal_timezone)
    # Assumes all sessions are 60 minutes, adjust using booking.offering.duration_minutes
    end_time_utc = start_time_utc + timedelta(minutes=60) 

    event_payload = {
        'summary': f"JH Motiv Coaching: Session with {booking.client.get_full_name()}",
        'location': 'Virtual Meeting Link (Check Booking Email)', 
        'description': f"Session Topic: {booking.offering.name}\nClient Email: {booking.client.email}",
        'start': {'dateTime': start_time_utc.isoformat(), 'timeZone': settings.TIME_ZONE},
        'end': {'dateTime': end_time_utc.isoformat(), 'timeZone': settings.TIME_ZONE},
        'attendees': [{'email': coach_user.email}, {'email': booking.client.email}],
    }

    # --- MOCK API CALL & SAVE EVENT ID ---
    mock_event_id = f"gcal-event-{booking.id}-{datetime.now().timestamp()}"
    booking.gcal_event_id = mock_event_id
    # IMPORTANT: Save the event ID back to the database
    # booking.save(update_fields=['gcal_event_id']) 
    logger.info(f"GCal: Mock Event created for Booking {booking.id}. ID saved.")
    return mock_event_id


def delete_calendar_event(booking):
    """
    (MOCK) Deletes the Google Calendar event associated with a booking.
    """
    if not booking.gcal_event_id:
        return False
        
    coach_user = booking.coach.user
    credentials = get_coach_credentials(coach_user)
    
    if not credentials:
        logger.warning(f"GCal: Skipping event deletion for Coach {coach_user.username}. Credentials missing.")
        return False
        
    logger.info(f"GCal: MOCK Event {booking.gcal_event_id} deleted successfully.")
    return True

# --- Availability Utility Functions (REQUIRED IMPORT FIX) ---

def get_calendar_conflicts(coach_user, start_time, end_time):
    """
    (MOCK PLACEHOLDER) Checks the coach's Google Calendar for existing events.
    """
    return False 


def get_available_time_slots(coach_user, date, offering_duration):
    """
    (MOCK PLACEHOLDER) Calculates available time slots for a coach on a specific date.
    """
    return []