import json
from django.shortcuts import redirect, reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from django.utils import timezone

from .models import GoogleCredentials
from accounts.models import CoachProfile


@login_required
def google_calendar_init(request):
    if 'code' in request.GET:
        return google_calendar_redirect(request)
    client_config = {
        "web": {
            "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH2_REDIRECT_URI],
        }
    }
    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/meetings.space.created",
        ],
        redirect_uri=settings.GOOGLE_OAUTH2_REDIRECT_URI
    )

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )

    request.session['oauth_state'] = state
    return redirect(authorization_url)


@login_required
def google_calendar_redirect(request):
    state = request.session.pop('oauth_state', '')

    client_config = {
        "web": {
            "client_id": settings.GOOGLE_OAUTH2_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH2_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.GOOGLE_OAUTH2_REDIRECT_URI],
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=[
            "https://www.googleapis.com/auth/calendar.events",
            "https://www.googleapis.com/auth/meetings.space.created",
        ],
        redirect_uri=settings.GOOGLE_OAUTH2_REDIRECT_URI,
        state=state
    )

    flow.fetch_token(authorization_response=request.build_absolute_uri())

    credentials = flow.credentials

    # Ensure the user is marked as a coach before getting/creating the profile.
    if not request.user.is_coach:
        request.user.is_coach = True
        request.user.save()

    # Get or create a CoachProfile for the current user
    coach_profile, created = CoachProfile.objects.get_or_create(user=request.user)

    # Create or update the GoogleCredentials object
    GoogleCredentials.objects.update_or_create(
        coach=coach_profile,
        defaults={
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_expiry': credentials.expiry,
            'scopes': ' '.join(credentials.scopes),
            'calendar_id': 'primary'  # Default to primary calendar
        }
    )

    return redirect(reverse('accounts:account_profile'))


@login_required
def google_calendar_disconnect(request):
    """
    Disconnects the user's Google Calendar by deleting their stored credentials.
    """
    try:
        coach_profile = request.user.coachprofile
        if hasattr(coach_profile, 'google_credentials'):
            coach_profile.google_credentials.delete()
    except CoachProfile.DoesNotExist:
        # If the user is not a coach, there's nothing to disconnect.
        pass
    return redirect(reverse('accounts:account_profile'))

from django.http import JsonResponse
from datetime import datetime, time

from .utils import get_calendar_conflicts


def get_coach_availability(request, coach_id):
    """
    Returns a JSON response with the coach's availability for a given date range.
    """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if not all([start_date_str, end_date_str]):
        return JsonResponse({'error': 'start_date and end_date are required'}, status=400)

    try:
        start_date = datetime.fromisoformat(start_date_str)
        end_date = datetime.fromisoformat(end_date_str)
    except ValueError:
        return JsonResponse({'error': 'Invalid date format. Use ISO format.'}, status=400)

    try:
        coach_profile = CoachProfile.objects.get(id=coach_id)
    except CoachProfile.DoesNotExist:
        return JsonResponse({'error': 'Coach not found'}, status=404)

    conflicts = get_calendar_conflicts(coach_profile, start_date, end_date)

    # This is a simplified availability calculation. A more robust solution
    # would consider the coach's working hours, buffer times, etc.
    
    # For now, just return the conflicts
    return JsonResponse({'conflicts': conflicts})