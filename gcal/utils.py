import uuid
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def get_calendar_service(coach_profile):
    """Builds and returns a Google Calendar API service object."""
    credentials = coach_profile.google_credentials
    if not credentials or not credentials.access_token:
        return None

    # Create Google Credentials object
    google_credentials = Credentials(
        token=credentials.access_token,
        refresh_token=credentials.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_OAUTH2_CLIENT_ID,
        client_secret=settings.GOOGLE_OAUTH2_CLIENT_SECRET,
        scopes=credentials.scopes.split(' ')
    )

    # Refresh token if expired
    if google_credentials.expired and google_credentials.refresh_token:
        google_credentials.refresh(Request())
        # Update the stored credentials
        credentials.access_token = google_credentials.token
        credentials.token_expiry = timezone.now() + timedelta(seconds=google_credentials.expires_in)
        credentials.save()

    return build('calendar', 'v3', credentials=google_credentials)


def get_calendar_conflicts(coach_profile, start_time, end_time):
    """
    Fetches busy times from a coach's Google Calendar between a start and end time.
    """
    service = get_calendar_service(coach_profile)
    if not service:
        return []

    calendar_id = coach_profile.google_credentials.calendar_id or 'primary'
    
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=start_time.isoformat(),
        timeMax=end_time.isoformat(),
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    return events_result.get('items', [])

def create_calendar_event(coach_profile, summary, description, start_time, end_time, attendees=None):
    """
    Creates a new event in the coach's Google Calendar with a Google Meet link.
    """
    service = get_calendar_service(coach_profile)
    if not service:
        return None

    calendar_id = coach_profile.google_credentials.calendar_id or 'primary'

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': attendees if attendees else [],
        'reminders': {
            'useDefault': True,
        },
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        }
    }

    try:
        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
            sendNotifications=True,
            conferenceDataVersion=1
        ).execute()
        return created_event
    except HttpError as e:
        print(f"Error creating event: {e}")
        return None


def update_calendar_event(coach_profile, event_id, summary, description, start_time, end_time, attendees=None):
    """
    Updates an existing event. Uses patch to preserve existing Meet links, 
    and attempts to add one if missing.
    """
    service = get_calendar_service(coach_profile)
    if not service:
        return None

    calendar_id = coach_profile.google_credentials.calendar_id or 'primary'

    event_body = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC',
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
        'attendees': attendees if attendees else [],
        # Adding conferenceData here ensures that if the event LOST its link 
        # (or never had one), a new one is generated. 
        # If one already exists, this createRequest is safely ignored by Google.
        'conferenceData': {
            'createRequest': {
                'requestId': str(uuid.uuid4()),
                'conferenceSolutionKey': {
                    'type': 'hangoutsMeet'
                }
            }
        }
    }

    try:
        # Changed from .update() to .patch() to avoid overwriting unrelated fields
        updated_event = service.events().patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=event_body,
            sendNotifications=True,
            conferenceDataVersion=1
        ).execute()
        return updated_event
        
    except HttpError as e:
        # If event is not found (404) or gone (410), recreate it (Recover from manual deletion)
        if e.resp.status in [404, 410]:
            return create_calendar_event(
                coach_profile, summary, description, start_time, end_time, attendees
            )
        print(f"Error updating event: {e}")
        return None


def delete_calendar_event(coach_profile, event_id):
    """
    Deletes an event from the coach's Google Calendar.
    """
    service = get_calendar_service(coach_profile)
    if not service:
        return

    calendar_id = coach_profile.google_credentials.calendar_id or 'primary'

    try:
        service.events().delete(
            calendarId=calendar_id,
            eventId=event_id,
            sendNotifications=True
        ).execute()
    except HttpError as e:
        # If it's already deleted (404/410), that's fine.
        if e.resp.status in [404, 410]:
            pass
        else:
            print(f"Error deleting event: {e}")