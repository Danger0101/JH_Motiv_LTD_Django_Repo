from datetime import time
from .models import CoachAvailability, DateOverride, CoachVacation


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