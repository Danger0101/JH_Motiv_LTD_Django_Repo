from googleapiclient.discovery import build
from django.utils import timezone
from ..models import CoachBusySlot
import logging

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    
    def __init__(self, coach):
        self.coach = coach
        self.creds = self._get_credentials(coach) 
        if self.creds:
            self.service = build('calendar', 'v3', credentials=self.creds)
        else:
            self.service = None

    def _get_credentials(self, coach):
        # Placeholder for OAuth credential retrieval logic
        # In a real app, this would fetch tokens from the User model or a related OAuth model
        # For now, returning None or mocking if needed. 
        # Assuming the project has a way to get this, e.g., coach.user.google_credentials
        return None 

    def push_booking(self, booking):
        """
        Creates an event in the Coach's primary calendar.
        """
        if not self.service:
            logger.warning(f"No Google Credentials for coach {self.coach}")
            return None

        event_body = {
            'summary': f"Client Session: {booking.guest_name or (booking.client.first_name if booking.client else 'Guest')}",
            'description': f"Booking ID: {booking.id}",
            'start': {'dateTime': booking.start_datetime.isoformat()},
            'end': {'dateTime': booking.end_datetime.isoformat()},
            'attendees': [{'email': booking.guest_email or (booking.client.email if booking.client else '')}],
            'reminders': {'useDefault': True},
        }

        event = self.service.events().insert(calendarId='primary', body=event_body).execute()
        return event['id']

    def sync_busy_slots(self, days=30):
        """
        Fetches 'busy' times from Google and updates the local cache.
        """
        if not self.service:
            return

        now = timezone.now()
        end = now + timezone.timedelta(days=days)

        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": "primary"}]
        }
        
        events_result = self.service.freebusy().query(body=body).execute()
        busy_periods = events_result['calendars']['primary']['busy']

        # Sync to DB: Wipe & Replace for the window
        CoachBusySlot.objects.filter(
            coach=self.coach, 
            start_time__gte=now, 
            start_time__lte=end
        ).delete()

        new_slots = []
        for period in busy_periods:
            new_slots.append(CoachBusySlot(
                coach=self.coach,
                external_id=f"gcal_busy_{period['start']}", 
                start_time=period['start'],
                end_time=period['end']
            ))
        
        CoachBusySlot.objects.bulk_create(new_slots)