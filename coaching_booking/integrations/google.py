from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from django.conf import settings
from django.utils import timezone
from ..models import CoachBusySlot
import logging

logger = logging.getLogger(__name__)

class GoogleCalendarService:
    
    def __init__(self, coach):
        self.coach = coach
        self.creds = self._get_credentials(coach)
        # Default to 'primary' unless DB says otherwise
        self.calendar_id = 'primary'
        if self.creds:
            self.service = build('calendar', 'v3', credentials=self.creds)
        else:
            self.service = None

    def _get_credentials(self, coach):
        """
        Retrieves OAuth credentials from the Coach's GoogleCredentials model.
        """
        try:
            db_creds = getattr(coach, 'google_credentials', None)
            
            if not db_creds:
                logger.info(f"No Google credentials linked for coach {coach.user.email}")
                return None
            
            # Capture the correct calendar ID if set
            if db_creds.calendar_id:
                self.calendar_id = db_creds.calendar_id

            creds = Credentials(
                token=db_creds.access_token,
                refresh_token=db_creds.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
                client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
                scopes=db_creds.scopes.split(' ') if db_creds.scopes else []
            )

            # Auto-Refresh Logic: Ensure token is valid before use and save updates to DB
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Update the DB with the new access token
                    db_creds.access_token = creds.token
                    db_creds.save(update_fields=['access_token'])
                    logger.info(f"Refreshed and saved Google Access Token for coach {coach.user.email}")
                except Exception as e:
                    logger.error(f"Failed to refresh token for coach {coach.user.email}: {e}")
            
            return creds
        except Exception as e:
            logger.error(f"Error retrieving credentials for coach {coach.id}: {e}")
            return None

    def push_booking(self, booking):
        """
        Creates an event in the Coach's calendar.
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
            summary = f"Workshop: {booking.workshop.name}"
            description += f"\nWorkshop: {booking.workshop.name}"
        elif booking.enrollment:
            # FIX: Access offering via enrollment
            description += f"\nOffering: {booking.enrollment.offering.name}"

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

        if client_email:
            event_body['attendees'].append({'email': client_email})

        try:
            # 4. API Call
            event = self.service.events().insert(
                calendarId=self.calendar_id,
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

    def delete_booking(self, gcal_event_id):
        if not self.service or not gcal_event_id:
            return False

        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=gcal_event_id,
                sendUpdates='all' 
            ).execute()
            logger.info(f"GCal Event deleted: {gcal_event_id}")
            return True
        except Exception as e:
            # 410 Gone means it's already deleted, which is fine
            if hasattr(e, 'resp') and e.resp.status == 410:
                return True
            logger.error(f"Failed to delete GCal event {gcal_event_id}: {e}")
            return False

    def update_booking(self, booking):
        """
        Updates an existing event in the Coach's calendar.
        Uses PATCH to preserve existing data like Google Meet links.
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
            summary = f"Workshop: {booking.workshop.name}"
            description += f"\nWorkshop: {booking.workshop.name}"
        elif booking.enrollment:
            description += f"\nOffering: {booking.enrollment.offering.name}"

        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': booking.start_datetime.isoformat()},
            'end': {'dateTime': booking.end_datetime.isoformat()},
            # We construct attendees list but only send it if needed. 
            # Ideally with PATCH we might check if we want to overwrite attendees.
            'attendees': [{'email': client_email}] if client_email else [],
            'reminders': {'useDefault': True},
        }

        try:
            # CHANGED: Use patch() instead of update()
            # This updates only the fields provided in event_body, preserving conferenceData
            event = self.service.events().patch(
                calendarId=self.calendar_id,
                eventId=booking.gcal_event_id, 
                body=event_body,
                sendUpdates='all'
            ).execute()
            return event['id']
        except Exception as e:
            logger.error(f"Failed to update booking {booking.id} in GCal: {e}")
            return None

    def sync_busy_slots(self, days=30):
        if not self.service:
            return

        now = timezone.now()
        end = now + timezone.timedelta(days=days)

        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": self.calendar_id}]
        }
        
        try:
            events_result = self.service.freebusy().query(body=body).execute()
            busy_periods = events_result['calendars'][self.calendar_id]['busy']

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