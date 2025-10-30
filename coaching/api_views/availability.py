# coaching/api_views/availability.py

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
import json
import datetime
from ..models import RecurringAvailability, SpecificAvailability, CoachVacationBlock 
from ..utils import coach_is_valid
from django.db.models import Q
import calendar
from datetime import date, timedelta
import pytz


# =======================================================
# CALENDAR HELPERS (NEWLY MODULARIZED)
# =======================================================

def get_nav_dates(year, month):
    """Calculates the current, previous, and next month objects for calendar navigation."""
    current_month_obj = datetime.date(year, month, 1)

    # Calculate previous month object
    prev_month_date = current_month_obj - timedelta(days=1)
    prev_month_obj = prev_month_date.replace(day=1)

    # Calculate next month object
    # Add 32 days to the first of the current month to ensure we land in the next month
    next_month_obj = (current_month_obj + timedelta(days=32)).replace(day=1)
    
    return current_month_obj, prev_month_obj, next_month_obj


def build_availability_grid(coach, year, month, current_month_obj, today):
    """Fetches all availability data and merges it into a single calendar grid structure."""
    
    # 3. Calculate calendar grid dates (Start Monday)
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days_grid = cal.monthdatescalendar(year, month)
    
    start_of_period = month_days_grid[0][0]
    end_of_period = month_days_grid[-1][-1]
    
    # --- Data Fetching ---
    recurring_map = {
        r.day_of_week: {'start': r.start_time, 'end': r.end_time, 'available': r.is_available}
        for r in RecurringAvailability.objects.filter(coach=coach)
    }

    specific_map = {
        s.date: {'start': s.start_time, 'end': s.end_time, 'available': s.is_available}
        for s in SpecificAvailability.objects.filter(
            coach=coach, 
            date__range=(start_of_period, end_of_period)
        )
    }
    
    vacation_list = CoachVacationBlock.objects.filter(
        coach=coach, 
        start_date__lte=end_of_period,
        end_date__gte=start_of_period
    ).values_list('start_date', 'end_date')

    def is_on_vacation(day_date):
        for start, end in vacation_list:
            if start <= day_date <= end:
                return True
        return False
        
    # --- Merging Logic ---
    final_grid = []

    for week in month_days_grid:
        week_data = []
        for day_date in week:
            day_of_week_num = day_date.weekday() # 0=Monday, 6=Sunday
            
            merged_day = {
                'day': day_date,
                'is_current_month': day_date.month == current_month_obj.month,
                'is_today': day_date == today,
                'is_vacation': False,
                'is_specific': False,
                'available_slots': []
            }
            
            # Priority 1: Vacation Block (Highest priority block)
            if is_on_vacation(day_date):
                merged_day['is_vacation'] = True
                week_data.append(merged_day)
                continue

            # Priority 2: Specific Availability Override
            specific_slot = specific_map.get(day_date)
            
            if specific_slot:
                merged_day['is_specific'] = True
                
                if specific_slot['available']:
                    merged_day['available_slots'] = [{
                        'start_time': specific_slot['start'].strftime("%I:%M %p"),
                        'end_time': specific_slot['end'].strftime("%I:%M %p"),
                    }]
                
            # Priority 3: Recurring Schedule (if no specific override exists)
            elif day_date.month == current_month_obj.month:
                base_slot = recurring_map.get(day_of_week_num)
                if base_slot and base_slot['available']:
                    merged_day['available_slots'] = [{
                        'start_time': base_slot['start'].strftime("%I:%M %p"),
                        'end_time': base_slot['end'].strftime("%I:%M %p"),
                    }]
            
            week_data.append(merged_day)
        final_grid.append(week_data)
    
    return final_grid

# =======================================================
# Recurring Availability View
# =======================================================

@login_required
@require_http_methods(["GET", "POST"])
def coach_recurring_availability_view(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    if request.method == 'GET':
        schedule = RecurringAvailability.objects.filter(coach=coach).order_by('day_of_week', 'start_time')
        data = []
        for slot in schedule:
            data.append({
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "is_available": slot.is_available,
            })
        
        # Retrieve timezone string safely
        timezone_obj = getattr(coach, 'user_timezone', timezone.get_current_timezone())
        timezone_str = str(timezone_obj) 

        context = {
            'schedule': json.dumps(data), 
            'timezone': timezone_str 
        }
        return render(request, 'coaching/partials/recurring_availability_manager.html', context)

    elif request.method == 'POST':
        try:
            if request.content_type == 'application/x-www-form-urlencoded':
                return JsonResponse({"error": "Please submit availability as JSON data."}, status=400)
            
            data = json.loads(request.body)
            new_slots = data.get('schedule', [])

            with transaction.atomic():
                RecurringAvailability.objects.filter(coach=coach).delete()
                
                for slot in new_slots:
                    day = int(slot['day_of_week'])
                    start = datetime.time.fromisoformat(slot['start_time'])
                    end = datetime.time.fromisoformat(slot['end_time'])
                    
                    if start >= end and slot.get('is_available', True):
                        raise ValueError(f"Start time {slot['start_time']} cannot be after or equal to end time.")
                    
                    RecurringAvailability.objects.create(
                        coach=coach, day_of_week=day, start_time=start, end_time=end,
                        is_available=slot.get('is_available', True)
                    )

            # Add HX-Trigger to update the calendar after saving the recurring schedule
            response = JsonResponse({"success": True, "message": "Weekly schedule updated successfully."}, status=200)
            response['HX-Trigger'] = 'recurring-schedule-updated'
            return response
        
        except ValueError as e:
            return JsonResponse({"error": f"Validation Error: {e}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {e}"}, status=500)


# =======================================================
# SPECIFIC AVAILABILITY API (One-Off Adjustments)
# =======================================================
# ... (coach_specific_availability_view and coach_specific_availability_detail remain unchanged)
@login_required
@require_http_methods(["GET", "POST"])
def coach_specific_availability_view(request):
    """
    Handles listing (GET) and creating (POST) specific, one-off availability slots/blocks.
    GET returns the HTML fragment for the list.
    """
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    if request.method == 'GET':
        # Retrieve and filter future specific slots
        slots = SpecificAvailability.objects.filter(
            coach=coach, 
            date__gte=timezone.now().date()
        ).order_by('date', 'start_time')
        
        # 🛑 FIX 2: Returns the HTMX fragment to list the slots
        return render(request, 'coaching/partials/specific_slots_list_fragment.html', {'specific_slots': slots})

    elif request.method == 'POST':
        try:
            # Assumes form data submission from the HTMX form
            data = request.POST
            date = datetime.date.fromisoformat(data['date'])
            start = datetime.time.fromisoformat(data['start_time'])
            end = datetime.time.fromisoformat(data['end_time'])
            # Checkbox returns 'on'/'off' or radio returns 'true'/'false'
            is_available = data.get('is_available') in ['true', 'on']
            
            if start >= end:
                raise ValueError("Start time cannot be after or equal to end time.")
            if date < timezone.now().date():
                raise ValueError("Cannot schedule specific slots for dates in the past.")

            # Create the block
            SpecificAvailability.objects.create(
                coach=coach,
                date=date,
                start_time=start,
                end_time=end,
                is_available=is_available
            )
            
            # HTMX Response: Trigger refresh of the list container AND the calendar
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'specific-slot-updated'
            return response
        
        except Exception as e:
            # Use HTTPResponse to return an error message that HTMX can display
            return HttpResponse(f"Error: Invalid data format or value: {e}", status=400)


@login_required
@require_http_methods(["DELETE"])
def coach_specific_availability_detail(request, slot_id):
    """API endpoint to delete a specific one-off availability slot."""
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    # Use get_object_or_404 to ensure the slot exists AND belongs to the coach
    get_object_or_404(
        SpecificAvailability,
        pk=slot_id,
        coach=request.user
    ).delete()

    # 🛑 FIX 3: Returns an HTMX trigger response
    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'specific-slot-updated'
    return response

# =======================================================
# MODAL & DYNAMIC AVAILABILITY CREATION
# =======================================================

@login_required
@require_http_methods(["GET"])
def coach_add_availability_modal_view(request):
    """Serves the HTML for the 'Add Availability' modal."""
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.date.fromisoformat(date_str)
        day_name = selected_date.strftime('%A') # e.g., "Monday"
    except (ValueError, TypeError):
        return HttpResponse("Invalid date provided.", status=400)

    context = {
        'date_str': date_str,
        'selected_date': selected_date,
        'day_name': day_name,
    }
    return render(request, 'coaching/partials/add_availability_modal.html', context)


@login_required
@require_http_methods(["POST"])
def coach_create_availability_from_modal_view(request):
    """
    Handles the form submission from the availability modal.
    Creates either a Specific or Recurring availability slot.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    try:
        coach = request.user
        data = request.POST
        availability_type = data.get('availability_type')
        date = datetime.date.fromisoformat(data['date'])
        start_time = datetime.time.fromisoformat(data['start_time'])
        end_time = datetime.time.fromisoformat(data['end_time'])

        if start_time >= end_time:
            raise ValueError("Start time must be before end time.")

        if availability_type == 'specific':
            SpecificAvailability.objects.create(
                coach=coach, date=date, start_time=start_time, end_time=end_time, is_available=True
            )
            # Trigger update for specific slots list and calendar
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'specific-slot-updated'
            return response

        elif availability_type == 'recurring':
            day_of_week = date.weekday() # 0=Monday, 6=Sunday
            RecurringAvailability.objects.update_or_create(
                coach=coach,
                day_of_week=day_of_week,
                defaults={'start_time': start_time, 'end_time': end_time, 'is_available': True}
            )
            # Trigger update for recurring schedule UI and calendar
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'recurring-schedule-updated'
            return response
            
        else:
            raise ValueError("Invalid availability type specified.")

    except Exception as e:
        return HttpResponse(f"Error: {e}", status=400)

# =======================================================
# CALENDAR VIEW (Simplified)
# =======================================================

@login_required
@require_http_methods(["GET"])
def coach_calendar_view(request):
    """
    Renders the interactive monthly calendar grid showing merged availability,
    using helper functions to keep the main view logic clean.
    """
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    # 1. Determine which month to display
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    
    # 2. Set the coach's timezone & today's date
    coach_tz = pytz.timezone(str(getattr(coach, 'user_timezone', timezone.get_current_timezone())))
    today = now.astimezone(coach_tz).date()

    # 3. Modularized Date Calculation
    current_month_obj, prev_month_obj, next_month_obj = get_nav_dates(year, month)
    
    # Calculate if the previous month is in the past relative to today
    prev_month_is_past = (prev_month_obj.year < today.year) or \
                         (prev_month_obj.year == today.year and prev_month_obj.month < today.month)

    # 4. Modularized Grid Building (Merging Logic)
    final_grid = build_availability_grid(coach, year, month, current_month_obj, today)
    
    # 5. Build the final context
    context = {
        'month_days': final_grid, 
        'current_month': current_month_obj,
        'coach_tz': coach_tz.zone,
        'prev_month': prev_month_obj,
        'next_month': next_month_obj,
        'today_date': today,
        'prev_month_is_past': prev_month_is_past, # Pass the pre-calculated boolean
        'day_names': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    }
    
    # 6. Render the Calendar Template
    return render(request, 'coaching/partials/calendar_grid_fragment.html', context)