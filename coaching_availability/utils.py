from datetime import time, datetime, timedelta, date
from .models import CoachAvailability, DateOverride, CoachVacation
from collections import defaultdict
from gcal.models import GoogleCredentials
from accounts.models import CoachProfile
from coaching_booking.models import SessionBooking # Import SessionBooking

# Helper functions for time conversion
def _time_to_minutes(t):
    """Converts a datetime.time object to minutes since midnight."""
    return t.hour * 60 + t.minute

def _minutes_to_time(minutes):
    """Converts minutes since midnight to a datetime.time object."""
    hour = minutes // 60
    minute = minutes % 60
    return time(hour, minute)

def _get_daily_effective_blocks(coach_profile, current_date):
    """
    Returns a list of (start_minutes, end_minutes) tuples representing all
    effective available blocks for a given coach on a specific date,
    considering CoachAvailability and DateOverride.
    """
    # Use coach_profile.user as the ForeignKey in CoachVacation, DateOverride, CoachAvailability
    coach_user = coach_profile.user

    # 1. Check for vacation - if on vacation, no blocks are available
    if CoachVacation.objects.filter(
        coach=coach_user,
        start_date__lte=current_date,
        end_date__gte=current_date
    ).exists():
        return []

    # 2. Check for date override
    try:
        override = DateOverride.objects.get(coach=coach_user, date=current_date)
        if override.is_available:
            if override.start_time and override.end_time:
                # Override defines specific times
                return [(_time_to_minutes(override.start_time), _time_to_minutes(override.end_time))]
            else:
                # If is_available is true but no times, it means the coach is available for the whole day
                # from 00:00 to 23:59. This might be an explicit "available all day" override.
                # For now, let's make it 9 AM to 5 PM if no specific times are given in the override itself.
                # A better approach might be to query weekly availability if times are null.
                return [(_time_to_minutes(time(9,0)), _time_to_minutes(time(17,0)))]
        else:
            # Override explicitly makes coach unavailable
            return []
    except DateOverride.DoesNotExist:
        pass # No override, fall through to weekly availability

    # 3. Fall back to recurring availability
    day_of_week_int = current_date.weekday() # 0=Monday, 6=Sunday
    weekly_availabilities = CoachAvailability.objects.filter(
        coach=coach_user,
        day_of_week=day_of_week_int
    ).order_by('start_time')

    # Convert to minutes for easier processing
    effective_blocks = []
    for avail in weekly_availabilities:
        effective_blocks.append((_time_to_minutes(avail.start_time), _time_to_minutes(avail.end_time)))
    
    return effective_blocks


def get_coach_available_slots(coach_profile, start_date, end_date, session_length_minutes, offering_type='one_on_one'):
    """
    Generates available 15-minute time slots for a given coach within a date range,
    considering weekly availability, date overrides, vacations, and existing bookings.

    Args:
        coach_profile (CoachProfile): The coach whose availability is being checked.
        start_date (date): The start date for checking availability.
        end_date (date): The end date for checking availability.
        session_length_minutes (int): The duration of the session in minutes (e.g., 60, 90).
        offering_type (str): 'one_on_one' for individual sessions (blocks booked slots),
                             'workshop' for multi-person events (does not block booked slots).

    Returns:
        list: A list of datetime objects representing the start times of available slots.
    """
    if not isinstance(coach_profile, CoachProfile):
        raise TypeError("coach_profile must be an instance of CoachProfile.")

    available_slots = []
    current_date = start_date
    interval_minutes = 15

    # Fetch all existing bookings for the coach within the date range
    # Only consider existing bookings if it's a 'one_on_one' session to prevent double bookings
    booked_slots_in_minutes = defaultdict(list)
    if offering_type == 'one_on_one':
        booked_sessions = SessionBooking.objects.filter(
            coach=coach_profile,
            start_datetime__date__gte=start_date,
            start_datetime__date__lte=end_date,
            status='BOOKED' # Only consider 'BOOKED' sessions
        ).order_by('start_datetime')

        for booking in booked_sessions:
            booking_start_minutes = _time_to_minutes(booking.start_datetime.time())
            booking_end_minutes = _time_to_minutes(booking.end_datetime.time())
            booked_slots_in_minutes[booking.start_datetime.date()].append((booking_start_minutes, booking_end_minutes))

    while current_date <= end_date:
        daily_effective_blocks = _get_daily_effective_blocks(coach_profile, current_date)

        for block_start_minutes, block_end_minutes in daily_effective_blocks:
            # Iterate through the block in 15-minute intervals
            slot_start_minutes = block_start_minutes
            while slot_start_minutes + session_length_minutes <= block_end_minutes:
                slot_end_minutes = slot_start_minutes + session_length_minutes

                # Check for overlap with existing 1-on-one bookings ONLY if offering_type is 'one_on_one'
                is_booked = False
                if offering_type == 'one_on_one':
                    for booked_start, booked_end in booked_slots_in_minutes[current_date]:
                        # Overlap if: (potential_slot_start < booked_session_end AND potential_slot_end > booked_session_start)
                        if (slot_start_minutes < booked_end and slot_end_minutes > booked_start):
                            is_booked = True
                            break
                
                if not is_booked:
                    # Construct datetime objects for the available slot
                    slot_start_time = _minutes_to_time(slot_start_minutes)
                    slot_datetime = datetime.combine(current_date, slot_start_time)
                    available_slots.append(slot_datetime)
                
                slot_start_minutes += interval_minutes # Move to the next 15-minute interval
        
        current_date += timedelta(days=1)
    
    return available_slots


# Original function for backward compatibility or if still in use elsewhere
def get_availability_for_date(coach_user, date):
    """
    Returns valid time slots for a given coach (User object) and date.
    This is the old function, `_get_daily_effective_blocks` is more robust.
    """
    # This old function returned a single (start_time, end_time) tuple
    # It doesn't handle multiple blocks per day from CoachAvailability
    # or consider existing bookings. This is kept for reference or if
    # some old code still relies on its specific return type.
    
    # 1. Check for vacation
    if CoachVacation.objects.filter(
        coach=coach_user,
        start_date__lte=date,
        end_date__gte=date
    ).exists():
        return []

    # 2. Check for date override
    try:
        override = DateOverride.objects.get(coach=coach_user, date=date)
        if override.is_available:
            return [(override.start_time, override.end_time)] # Assuming override has times
        else:
            return [] # Override explicitly makes coach unavailable
    except DateOverride.DoesNotExist:
        pass

    # 3. Fall back to recurring availability
    day_of_week = date.weekday()  # 0=Monday, 6=Sunday
    try:
        availability = CoachAvailability.objects.filter(
            coach=coach_user,
            day_of_week=day_of_week
        ).first() # Use .first() to get one if multiple
        if availability:
            return [(availability.start_time, availability.end_time)]
        return []
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

    for day, day_name in CoachAvailability.DAYS_OF_WEEK:
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
        'google_calendar_connected': google_calendar_connected,
    }
    return context