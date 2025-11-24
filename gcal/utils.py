import uuid
from googleapiclient.discovery import build
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

    created_event = service.events().insert(
        calendarId=calendar_id,
        body=event,
        sendNotifications=True,
        conferenceDataVersion=1
    ).execute()

    return created_event


def update_calendar_event(coach_profile, event_id, summary, description, start_time, end_time, attendees=None):
    """
    Updates an existing event in the coach's Google Calendar.
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
    }

    updated_event = service.events().update(
        calendarId=calendar_id,
        eventId=event_id,
        body=event,
        sendNotifications=True,
        conferenceDataVersion=1
    ).execute()

    return updated_event


def delete_calendar_event(coach_profile, event_id):
    """
    Deletes an event from the coach's Google Calendar.
    """
    service = get_calendar_service(coach_profile)
    if not service:
        return

    calendar_id = coach_profile.google_credentials.calendar_id or 'primary'

    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
        sendNotifications=True
    ).execute()