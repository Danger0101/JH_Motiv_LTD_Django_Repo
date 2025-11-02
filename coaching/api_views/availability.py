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
# CALENDAR HELPERS
# =======================================================
def get_nav_dates(year, month):
    current_month_obj = datetime.date(year, month, 1)
    prev_month_date = current_month_obj - timedelta(days=1)
    prev_month_obj = prev_month_date.replace(day=1)
    next_month_obj = (current_month_obj + timedelta(days=32)).replace(day=1)
    return current_month_obj, prev_month_obj, next_month_obj


def build_availability_grid(coach, year, month, current_month_obj, today, user_tz):
    
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days_grid = cal.monthdatescalendar(year, month)
    
    start_of_period = month_days_grid[0][0]
    end_of_period = month_days_grid[-1][-1]

    coach_tz = pytz.timezone(str(getattr(coach, 'user_timezone', timezone.get_current_timezone())))
    
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
    ).values_list('start_date', 'end_date', 'override_allowed')

    def is_on_vacation(day_date):
        for start, end, override_allowed in vacation_list:
            if start <= day_date <= end:
                return (True, override_allowed)
        return (False, False)
        
    final_grid = []

    for week in month_days_grid:
        week_data = []
        for day_date in week:
            day_of_week_num = day_date.weekday()
            
            merged_day = {
                'day': day_date,
                'is_current_month': day_date.month == current_month_obj.month,
                'is_today': day_date == today,
                'is_vacation': False,
                'is_specific': False,
                'available_slots': []
            }
            
            on_vacation, override_allowed = is_on_vacation(day_date)
            if on_vacation and not override_allowed:
                merged_day['is_vacation'] = True
                week_data.append(merged_day)
                continue

            specific_slot = specific_map.get(day_date)
            
            if specific_slot:
                merged_day['is_specific'] = True
                
                if specific_slot['available']:
                    start_dt = coach_tz.localize(datetime.datetime.combine(day_date, specific_slot['start']))
                    end_dt = coach_tz.localize(datetime.datetime.combine(day_date, specific_slot['end']))
                    
                    user_start_dt = start_dt.astimezone(user_tz)
                    user_end_dt = end_dt.astimezone(user_tz)

                    merged_day['available_slots'] = [{
                        'start_time': user_start_dt.strftime("%I:%M %p"),
                        'end_time': user_end_dt.strftime("%I:%M %p"),
                    }]
                
            elif day_date.month == current_month_obj.month:
                base_slot = recurring_map.get(day_of_week_num)
                if base_slot and base_slot['available']:
                    start_dt = coach_tz.localize(datetime.datetime.combine(day_date, base_slot['start']))
                    end_dt = coach_tz.localize(datetime.datetime.combine(day_date, base_slot['end']))

                    user_start_dt = start_dt.astimezone(user_tz)
                    user_end_dt = end_dt.astimezone(user_tz)

                    merged_day['available_slots'] = [{
                        'start_time': user_start_dt.strftime("%I:%M %p"),
                        'end_time': user_end_dt.strftime("%I:%M %p"),
                    }]
            
            week_data.append(merged_day)
        final_grid.append(week_data)
    
    return final_grid
# =======================================================
# RECURRING AVAILABILITY
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
        
        context = {
            'schedule': json.dumps(data), 
        }
        return render(request, 'coaching/partials/_recurring_availability_form.html', context)

    elif request.method == 'POST':
        try:
            if 'application/json' not in request.content_type:
                return JsonResponse({"error": "Invalid content type. Please submit data as JSON."}, status=400)
            
            data = json.loads(request.body)
            new_schedule_slots = data.get('schedule', [])

            with transaction.atomic():
                for slot_data in new_schedule_slots:
                    day = int(slot_data['day_of_week'])
                    start_time = datetime.time.fromisoformat(slot_data['start_time'])
                    end_time = datetime.time.fromisoformat(slot_data['end_time'])
                    is_available = slot_data.get('is_available', False)
                    
                    if is_available and start_time >= end_time:
                        raise ValueError(f"On {calendar.day_name[day]}, start time must be before end time.")
                    
                    RecurringAvailability.objects.update_or_create(
                        coach=coach,
                        day_of_week=day,
                        defaults={
                            'start_time': start_time, 'end_time': end_time, 'is_available': is_available
                        }
                    )

            response = JsonResponse({"success": True, "message": "Weekly schedule updated successfully."}, status=200)
            response['HX-Trigger'] = 'recurring-schedule-updated'
            return response
        
        except ValueError as e:
            return JsonResponse({"error": f"Validation Error: {e}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"An unexpected error occurred: {e}"}, status=500)


# =======================================================
# SPECIFIC AVAILABILITY API
# =======================================================
@login_required
@require_http_methods(["GET", "POST"])
def coach_specific_availability_view(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    
    coach = request.user
    
    if request.method == 'GET':
        slots = SpecificAvailability.objects.filter(
            coach=coach, 
            date__gte=timezone.now().date()
        ).order_by('date', 'start_time')
        
        return render(request, 'coaching/partials/_specific_slots_list.html', {'specific_slots': slots})

    elif request.method == 'POST':
        try:
            data = request.POST
            date_obj = datetime.date.fromisoformat(data['date'])
            start_time = datetime.time.fromisoformat(data['start_time'])
            end_time = datetime.time.fromisoformat(data['end_time'])
            is_available = data.get('is_available') == 'true'
            
            if start_time >= end_time:
                raise ValueError("Start time must be before end time.")
            if date_obj < timezone.now().date():
                raise ValueError("Cannot schedule specific slots for dates in the past.")

            SpecificAvailability.objects.update_or_create(
                coach=coach, 
                date=date_obj, 
                defaults={
                    'start_time': start_time, 
                    'end_time': end_time, 
                    'is_available': is_available
                }
            )
            
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'specific-slot-updated'
            return response
        
        except Exception as e:
            return HttpResponse(f"Error: {e}", status=400)


@login_required
@require_http_methods(["DELETE"])
def coach_specific_availability_detail(request, slot_id):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    get_object_or_404(
        SpecificAvailability,
        pk=slot_id,
        coach=request.user
    ).delete()

    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'specific-slot-updated'
    return response

# =======================================================
# MODAL & DYNAMIC AVAILABILITY CREATION
# =======================================================

@login_required
@require_http_methods(["GET"])
def coach_add_availability_modal_view(request):
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    date_str = request.GET.get('date')
    try:
        selected_date = datetime.date.fromisoformat(date_str)
        day_name = selected_date.strftime('%A')
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
    if not coach_is_valid(request.user):
        return HttpResponse("Unauthorized", status=403)

    try:
        coach = request.user
        data = request.POST
        availability_type = data.get('availability_type')
        date_obj = datetime.date.fromisoformat(data['date'])
        start_time = datetime.time.fromisoformat(data['start_time'])
        end_time = datetime.time.fromisoformat(data['end_time'])

        if start_time >= end_time:
            raise ValueError("Start time must be before end time.")

        if availability_type == 'specific':
            is_available = data.get('is_available') == 'true'
            
            SpecificAvailability.objects.update_or_create(
                coach=coach, 
                date=date_obj, 
                defaults={
                    'start_time': start_time, 
                    'end_time': end_time, 
                    'is_available': is_available
                }
            )
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'specific-slot-updated'
            return response

        elif availability_type == 'recurring':
            day_of_week = date_obj.weekday()
            RecurringAvailability.objects.update_or_create(
                coach=coach,
                day_of_week=day_of_week,
                defaults={'start_time': start_time, 'end_time': end_time, 'is_available': True}
            )
            response = HttpResponse(status=201)
            response['HX-Trigger'] = 'recurring-schedule-updated'
            return response
            
        else:
            raise ValueError("Invalid availability type specified.")

    except Exception as e:
        return HttpResponse(f"Error: {e}", status=400)
# =======================================================
# CALENDAR VIEW
# =======================================================
@login_required
@require_http_methods(["GET"])
def coach_calendar_view(request):
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)
    coach = request.user
    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))
    coach_tz = pytz.timezone(str(getattr(coach, 'user_timezone', timezone.get_current_timezone())))
    today = now.astimezone(coach_tz).date()
    current_month_obj, prev_month_obj, next_month_obj = get_nav_dates(year, month)
    prev_month_is_past = (prev_month_obj.year < today.year) or \
                         (prev_month_obj.year == today.year and prev_month_obj.month < today.month)
    user_tz = pytz.timezone(str(getattr(request.user, 'user_timezone', timezone.get_current_timezone())))
    final_grid = build_availability_grid(coach, year, month, current_month_obj, today, user_tz)
    context = {
        'month_days': final_grid, 
        'current_month': current_month_obj,
        'coach_tz': coach_tz.zone,
        'user_tz': user_tz.zone,
        'prev_month': prev_month_obj,
        'next_month': next_month_obj,
        'today_date': today,
        'prev_month_is_past': prev_month_is_past,
        'day_names': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    }
    return render(
        request,
        'coaching/partials/calendar_grid_fragment.html',
        context
    )
