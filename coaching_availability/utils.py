from datetime import date, datetime, timedelta, time

from coaching_core.models import Offering
from gcal.utils import get_calendar_conflicts as get_coach_calendar_conflicts

from .models import CoachAvailability, CoachVacation


def calculate_bookable_slots(coach_id: int, offering_id: int, start_date: date, end_date: date) -> list[datetime]:
    """
    Calculates the final list of available booking slots for a specific coach and offering
    over a given date range. Slots must be exactly the length of the offering's session_length_minutes.
    """
    # 1. Retrieve Offering Data
    try:
        offering = Offering.objects.get(id=offering_id)
        session_length = timedelta(minutes=offering.session_length_minutes)
    except Offering.DoesNotExist:
        return []  # Return empty if the offering is not found

    final_slots = []
    
    # 2. Initialize Date Range
    current_date = start_date
    while current_date <= end_date:
        
        # 3. Check Vacation Block
        if CoachVacation.is_coach_on_vacation(coach_id, current_date):
            current_date += timedelta(days=1)
            continue  # Skip this day

        # 4. Get Base Availability
        day_of_week = current_date.weekday()  # Monday is 0 and Sunday is 6
        base_availability_ranges = CoachAvailability.get_available_time_ranges_for_day(coach_id, day_of_week)

        if not base_availability_ranges:
            current_date += timedelta(days=1)
            continue # Skip if no base availability for this day

        # 5. Get External Conflicts
        # This function needs to be robust to handle the full day's range
        day_start = datetime.combine(current_date, time.min)
        day_end = datetime.combine(current_date, time.max)
        external_conflicts = get_coach_calendar_conflicts(coach_id, day_start, day_end)

        # 6. Calculate Final Slots (Complex Logic Stub)
        # The following logic will iterate through the coach's standard working blocks,
        # subtract any conflicting events (from GCal), and then slice the remaining
        # continuous blocks of free time into discrete slots matching the session length.
        #
        # For each time_range in base_availability_ranges:
        #   a. Convert the time_range (time objects) into a datetime_range for the current_date.
        #   b. Initialize a list of 'free_blocks' with this initial datetime_range.
        #   c. For each conflict in external_conflicts:
        #      i. Iterate through the current 'free_blocks'.
        #      ii. If a conflict overlaps with a free_block, subtract the conflict. This may result
        #          in zero, one, or two smaller free_blocks.
        #      iii. Update the 'free_blocks' list with the new, smaller blocks.
        #   d. After all conflicts are processed, iterate through the final 'free_blocks'.
        #   e. For each final free_block, slice it into slots of 'session_length'.
        #      - Start at the beginning of the block.
        #      - While the current time + session_length <= end of the block:
        #          - Add the current time to 'final_slots'.
        #          - Increment current time by session_length.
        #
        # This stub represents a significant piece of interval arithmetic.
        
        # Placeholder for the logic described above
        pass


        current_date += timedelta(days=1)

    # 7. Return
    return final_slots
