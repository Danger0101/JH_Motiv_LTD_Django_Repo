from datetime import time, datetime, timedelta, date
from collections import defaultdict
from .models import CoachAvailability, DateOverride, CoachVacation
from accounts.models import CoachProfile
from coaching_booking.models import SessionBooking

def _time_to_minutes(t):
    """Converts a datetime.time object to minutes since midnight."""
    return t.hour * 60 + t.minute

def _minutes_to_time(minutes):
    """Converts minutes since midnight to a datetime.time object."""
    hour = minutes // 60
    minute = minutes % 60
    return time(hour, minute)

def get_coach_available_slots(coach_profile, start_date, end_date, session_length_minutes, offering_type='one_on_one'):
    """
    Optimized slot generation: Fetches all data in bulk to avoid N+1 query problems.
    """
    if not isinstance(coach_profile, CoachProfile):
        raise TypeError("coach_profile must be an instance of CoachProfile.")

    coach_user = coach_profile.user
    available_slots = []
    interval_minutes = 15

    # 1. PRE-FETCH ALL DATA (Reduces DB hits from ~300 to ~4)
    
    # Fetch Vacations in range
    vacations = CoachVacation.objects.filter(
        coach=coach_user,
        start_date__lte=end_date,
        end_date__gte=start_date
    )
    
    # Fetch Overrides in range
    overrides = DateOverride.objects.filter(
        coach=coach_user,
        date__range=[start_date, end_date]
    )
    overrides_map = {o.date: o for o in overrides}

    # Fetch Weekly Schedule
    weekly_schedule = CoachAvailability.objects.filter(coach=coach_user)
    schedule_by_day = defaultdict(list)
    for rule in weekly_schedule:
        schedule_by_day[rule.day_of_week].append(rule)

    # Fetch Booked Sessions (Only if blocking is required)
    booked_slots_map = defaultdict(list)
    if offering_type == 'one_on_one':
        booked_sessions = SessionBooking.objects.filter(
            coach=coach_profile,
            start_datetime__date__gte=start_date,
            start_datetime__date__lte=end_date,
            status__in=['BOOKED', 'RESCHEDULED', 'PENDING_PAYMENT']
        )
        for booking in booked_sessions:
            start_mins = _time_to_minutes(booking.start_datetime.time())
            end_mins = _time_to_minutes(booking.end_datetime.time())
            booked_slots_map[booking.start_datetime.date()].append((start_mins, end_mins))

    # 2. ITERATE DAYS (Processing in Memory)
    current_date = start_date
    while current_date <= end_date:
        # A. Check Vacation
        is_on_vacation = any(v.start_date <= current_date <= v.end_date for v in vacations)
        
        if not is_on_vacation:
            effective_blocks = []
            
            # B. Check Override (Priority)
            if current_date in overrides_map:
                override = overrides_map[current_date]
                if override.is_available:
                    if override.start_time and override.end_time:
                        effective_blocks.append((_time_to_minutes(override.start_time), _time_to_minutes(override.end_time)))
                    else:
                        # Default 9-5 if available=True but no time specified
                        effective_blocks.append((_time_to_minutes(time(9, 0)), _time_to_minutes(time(17, 0))))
            
            # C. Fallback to Weekly Schedule
            else:
                day_id = current_date.weekday()
                for rule in schedule_by_day.get(day_id, []):
                    effective_blocks.append((_time_to_minutes(rule.start_time), _time_to_minutes(rule.end_time)))

            # D. Generate Slots
            for block_start, block_end in effective_blocks:
                slot_start = block_start
                while slot_start + session_length_minutes <= block_end:
                    slot_end = slot_start + session_length_minutes
                    
                    # Collision Detection
                    is_booked = False
                    if offering_type == 'one_on_one':
                        for b_start, b_end in booked_slots_map[current_date]:
                            # Overlap Logic
                            if slot_start < b_end and slot_end > b_start:
                                is_booked = True
                                break
                    
                    if not is_booked:
                        slot_time = _minutes_to_time(slot_start)
                        available_slots.append(datetime.combine(current_date, slot_time))

                    slot_start += interval_minutes

        current_date += timedelta(days=1)

    return available_slots

# Keep legacy contexts/functions if referenced elsewhere
def get_weekly_schedule_context(request_user):
    """Prepares the context for rendering the weekly schedule forms."""
    # (This function logic remains the same as your previous upload)
    initial_data = []
    availabilities = CoachAvailability.objects.filter(coach=request_user).order_by('day_of_week', 'start_time')
    
    existing_data = defaultdict(list)
    for availability in availabilities:
        existing_data[availability.day_of_week].append({
            'start_time': availability.start_time,
            'end_time': availability.end_time,
        })

    from .models import CoachAvailability # Re-import inside function if needed or rely on top-level
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
            
    return {'google_calendar_connected': False} # Placeholder