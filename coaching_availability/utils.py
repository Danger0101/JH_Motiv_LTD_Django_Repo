from datetime import time
from .models import CoachAvailability, DateOverride, CoachVacation
from .forms import BaseWeeklyScheduleFormSet, DateOverrideForm, CoachVacationForm, DAYS_OF_WEEK
from collections import defaultdict
from gcal.models import GoogleCredentials
from accounts.models import CoachProfile # Assuming CoachProfile is in accounts.models or accessible


def get_availability_for_date(coach, date):
    """
    Returns valid time slots for a given coach and date.
    The hierarchy is:
    1. Vacation
    2. DateOverride
    3. CoachAvailability
    """

    # 1. Check for vacation
    if CoachVacation.objects.filter(
        coach=coach,
        start_date__lte=date,
        end_date__gte=date
    ).exists():
        return []

    # 2. Check for date override
    try:
        override = DateOverride.objects.get(coach=coach, date=date)
        if override.is_available:
            return [(override.start_time, override.end_time)]
        else:
            return []
    except DateOverride.DoesNotExist:
        pass

    # 3. Fall back to recurring availability
    day_of_week = date.weekday()  # 0=Monday, 6=Sunday
    try:
        availability = CoachAvailability.objects.get(
            coach=coach,
            day_of_week=day_of_week
        )
        return [(availability.start_time, availability.end_time)]
    except CoachAvailability.DoesNotExist:
        return []

calculate_bookable_slots = get_availability_for_date


def get_weekly_schedule_context(request_user):
    """
    Prepares the context for rendering the weekly schedule and availability forms.
    """
    initial_data = []
    availabilities = CoachAvailability.objects.filter(coach=request_user).order_by('day_of_week', 'start_time')
    
    existing_data = defaultdict(list)
    for availability in availabilities:
        existing_data[availability.day_of_week].append({
            'start_time': availability.start_time,
            'end_time': availability.end_time,
        })

    for day, day_name in DAYS_OF_WEEK:
        day_availabilities = existing_data[day]
        if day_availabilities:
            for availability in day_availabilities:
                initial_data.append({
                    'day_of_week': day,
                    'start_time': availability['start_time'],
                    'end_time': availability['end_time'],
                })
        else:
            initial_data.append({'day_of_week': day, 'start_time': None, 'end_time': None})

    google_calendar_connected = False
    if request_user.is_coach:
        try:
            coach_profile = request_user.coach_profile
            google_calendar_connected = GoogleCredentials.objects.filter(coach=coach_profile).exists()
        except CoachProfile.DoesNotExist:
            pass
            
    context = {
        'weekly_schedule_formset': BaseWeeklyScheduleFormSet(initial=initial_data),
        'days_of_week': DAYS_OF_WEEK,
        'override_form': DateOverrideForm(),
        'vacation_form': CoachVacationForm(),
        'google_calendar_connected': google_calendar_connected,
    }
    return context