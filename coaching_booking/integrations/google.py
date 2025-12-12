from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings
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
        """
        Retrieves OAuth credentials from the Coach's GoogleCredentials model.
        """
        try:
            # Access the related GoogleCredentials object
            # This relies on related_name='google_credentials' in gcal.models
            db_creds = getattr(coach, 'google_credentials', None)
            
            if not db_creds:
                logger.info(f"No Google credentials linked for coach {coach.user.email}")
                return None
            
            # Construct the google.oauth2.credentials.Credentials object
            return Credentials(
                token=db_creds.access_token,
                refresh_token=db_creds.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                scopes=db_creds.scopes.split(' ') if db_creds.scopes else []
            )
        except Exception as e:
            logger.error(f"Error retrieving credentials for coach {coach.id}: {e}")
            return None

    def push_booking(self, booking):
        """
        Creates an event in the Coach's primary calendar with a Google Meet link.
        """
        if not self.service:
            logger.warning(f"No Google Calendar service available for coach {self.coach}")
            return None

        # 1. Determine Client Details
        if booking.client:
            client_name = booking.client.get_full_name()
            client_email = booking.client.email
        else:
            client_name = booking.guest_name or "Guest"
            client_email = booking.guest_email

        # 2. Build Event Metadata
        summary = f"Coaching Session: {client_name}"
        description = f"Booking ID: {booking.id}\nClient: {client_name}"
        
        if booking.workshop:
            summary = f"Workshop: {booking.workshop.title}"
            description += f"\nWorkshop: {booking.workshop.title}"
        elif booking.offering:
            description += f"\nOffering: {booking.offering.name}"

        # 3. Construct Event Body
        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': booking.start_datetime.isoformat()},
            'end': {'dateTime': booking.end_datetime.isoformat()},
            'attendees': [],
            # Request Google Meet generation
            'conferenceData': {
                'createRequest': {
                    'requestId': f"booking_{booking.id}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                }
            },
            'reminders': {'useDefault': True},
        }

        # Add Client as Attendee (This puts the event on their calendar & sends invite)
        if client_email:
            event_body['attendees'].append({'email': client_email})

        try:
            # 4. API Call
            # conferenceDataVersion=1 is REQUIRED to generate the Meet link
            # sendUpdates='all' sends email notifications to the client
            event = self.service.events().insert(
                calendarId='primary', 
                body=event_body, 
                conferenceDataVersion=1,
                sendUpdates='all' 
            ).execute()
            
            meet_link = event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri', 'No Link')
            logger.info(f"GCal Event created: {event.get('id')} | Meet: {meet_link}")
            
            return event['id']

        except Exception as e:
            logger.error(f"Failed to push booking {booking.id} to GCal: {e}")
            return None

    def update_booking(self, booking):
        """
        Updates an existing event in the Coach's primary calendar.
        """
        if not self.service or not booking.gcal_event_id:
            return None

        # 1. Determine Client Details
        if booking.client:
            client_name = booking.client.get_full_name()
            client_email = booking.client.email
        else:
            client_name = booking.guest_name or "Guest"
            client_email = booking.guest_email

        # 2. Build Event Metadata
        summary = f"Coaching Session: {client_name}"
        description = f"Booking ID: {booking.id}\nClient: {client_name}"
        
        if booking.workshop:
            summary = f"Workshop: {booking.workshop.title}"
            description += f"\nWorkshop: {booking.workshop.title}"
        elif booking.offering:
            description += f"\nOffering: {booking.offering.name}"

        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': booking.start_datetime.isoformat()},
            'end': {'dateTime': booking.end_datetime.isoformat()},
            'attendees': [],
            'reminders': {'useDefault': True},
        }

        if client_email:
            event_body['attendees'].append({'email': client_email})

        try:
            # Use update (PUT) to overwrite the event details
            event = self.service.events().update(
                calendarId='primary', 
                eventId=booking.gcal_event_id, 
                body=event_body,
                sendUpdates='all'
            ).execute()
            return event['id']
        except Exception as e:
            logger.error(f"Failed to update booking {booking.id} in GCal: {e}")
            return None

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
        
        try:
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
            
        except Exception as e:
            logger.error(f"Error syncing busy slots for coach {self.coach}: {e}")