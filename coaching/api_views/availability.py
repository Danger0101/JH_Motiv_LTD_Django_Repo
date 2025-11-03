# coaching/api_views/availability.py

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django import forms
from django.forms import modelformset_factory
from django.contrib.auth import get_user_model
from django.db import transaction, models
from django.utils import timezone
import json
import datetime
from dateutil.parser import isoparse 
from ..models import RecurringAvailability, SpecificAvailability, CoachVacationBlock, CoachOffering, CoachingSession, SessionStatus
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


def build_availability_grid(coach, offering, year, month, current_month_obj, today, user_tz, program_start_date=None, program_end_date=None):
    
    cal = calendar.Calendar(firstweekday=calendar.MONDAY)
    month_days_grid = cal.monthdatescalendar(year, month)
    
    start_of_period = month_days_grid[0][0]
    end_of_period = month_days_grid[-1][-1]
    
    # Ensure program dates are date objects if they exist
    if isinstance(program_start_date, str):
        program_start_date = isoparse(program_start_date).date()
    if isinstance(program_end_date, str):
        program_end_date = isoparse(program_end_date).date()

    coach_tz_str = str(getattr(coach, 'user_timezone', timezone.get_current_timezone()))
    coach_tz = pytz.timezone(coach_tz_str)
    
    # --- Data Fetching ---
    # Fetch all recurring slots and group them by day of the week
    recurring_slots_by_day = [[] for _ in range(7)]
    for r in RecurringAvailability.objects.filter(coach=coach):
        recurring_slots_by_day[r.day_of_week].append({'start': r.start_time, 'end': r.end_time})

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

    # Fetch existing sessions to block out those times
    existing_sessions = CoachingSession.objects.filter(
        coach=coach,
        start_time__range=(coach_tz.localize(datetime.datetime.combine(start_of_period, datetime.time.min)),
                           coach_tz.localize(datetime.datetime.combine(end_of_period, datetime.time.max))),
        status__in=[SessionStatus.BOOKED, SessionStatus.PENDING]
    ).values_list('start_time', 'end_time')

    def is_on_vacation(day_date):
        for start, end, override_allowed in vacation_list:
            if start <= day_date <= end:
                return (True, override_allowed)
        return (False, False)
        
    final_grid = []

    # Convert existing session times to a set of start times for quick lookup
    booked_slots_utc = set()
    for start, end in existing_sessions:
        booked_slots_utc.add(start.astimezone(pytz.utc))

    def generate_slots(day_date, start_time, end_time):
        """Generate bookable slots for a given time range."""
        # This should only run for offerings with a minute duration
        if not offering.duration_minutes:
            return []
        session_duration = datetime.timedelta(minutes=offering.duration_minutes)
        slots = []
        current_time = coach_tz.localize(datetime.datetime.combine(day_date, start_time))
        end_datetime = coach_tz.localize(datetime.datetime.combine(day_date, end_time))

        # Ensure we don't generate slots in the past
        now_in_coach_tz = timezone.now().astimezone(coach_tz)

        while current_time + session_duration <= end_datetime:
            # Check if slot is in the future
            if current_time < now_in_coach_tz:
                current_time += session_duration
                continue

            # Check for conflicts with existing sessions
            if current_time.astimezone(pytz.utc) in booked_slots_utc:
                current_time += session_duration
                continue

            user_start_dt = current_time.astimezone(user_tz)
            slots.append({
                'start_time_iso': current_time.isoformat(),
                'start_time_display': user_start_dt.strftime("%I:%M %p"),
            })
            current_time += session_duration
        
        return slots



    for week in month_days_grid:
        week_data = []
        for day_date in week:
            day_of_week_num = day_date.weekday()
            
            merged_day = {
                'day': day_date,
                'is_current_month': day_date.month == current_month_obj.month,
                'is_today': day_date == today,
                'is_vacation': False,
                'is_outside_program': False,
                'is_specific': False,
                'is_bookable_full_day': False,
                'available_slots': []
            }

            # Check if the day is outside the user's program validity dates
            if (program_start_date and day_date < program_start_date) or \
               (program_end_date and day_date > program_end_date):
                merged_day['is_outside_program'] = True
                week_data.append(merged_day)
                continue
            
            on_vacation, override_allowed = is_on_vacation(day_date)
            if on_vacation and not override_allowed:
                merged_day['is_vacation'] = True
                week_data.append(merged_day)
                continue
            
            # Handle Full-Day vs. Slot-Based Offerings
            if offering.is_full_day:
                # For full-day offerings, check if the day is free
                day_has_sessions = any(s.astimezone(coach_tz).date() == day_date for s in booked_slots_utc)
                if not day_has_sessions and day_date >= today:
                    merged_day['is_bookable_full_day'] = True
            else:
                # For slot-based offerings, generate time slots
                specific_slot = specific_map.get(day_date)
                if specific_slot:
                    merged_day['is_specific'] = True
                    if specific_slot['available']:
                        merged_day['available_slots'] = generate_slots(day_date, specific_slot['start'], specific_slot['end'])
                else:
                    # Iterate over all recurring slots for this day of the week
                    all_slots_for_day = []
                    for base_slot in recurring_slots_by_day[day_of_week_num]:
                        all_slots_for_day.extend(generate_slots(day_date, base_slot['start'], base_slot['end']))
                    merged_day['available_slots'] = sorted(all_slots_for_day, key=lambda x: x['start_time_iso'])
            
            week_data.append(merged_day)
        final_grid.append(week_data)
    
    return final_grid

# =======================================================
# RECURRING AVAILABILITY
# =======================================================
@login_required
@require_http_methods(["GET", "POST"])
def coach_recurring_availability_view(request):
    """
    Handles GET and POST for a coach's recurring availability using a Django FormSet.
    """
    if not coach_is_valid(request.user):
        return JsonResponse({"error": "Unauthorized access."}, status=403)

    coach = request.user

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            schedule_data = data.get('schedule', [])

            with transaction.atomic():
                # Delete old schedule
                RecurringAvailability.objects.filter(coach=coach).delete()

                # Create new schedule from payload
                for day_index, day_data in enumerate(schedule_data):
                    for slot in day_data['slots']:
                        start_time = datetime.time.fromisoformat(slot['start'])
                        end_time = datetime.time.fromisoformat(slot['end'])

                        if start_time >= end_time:
                            raise ValueError(f"On {day_data['name']}, start time must be before end time.")

                        RecurringAvailability.objects.create(
                            coach=coach,
                            day_of_week=day_index,
                            start_time=start_time,
                            end_time=end_time,
                            is_available=True # is_available is now implicit by the slot's existence
                        )

            # After saving, re-render the form with the new data and a success message
            new_schedule = [[] for _ in range(7)]
            for slot in RecurringAvailability.objects.filter(coach=coach).order_by('start_time'):
                new_schedule[slot.day_of_week].append({
                    'start': slot.start_time.strftime('%H:%M'),
                    'end': slot.end_time.strftime('%H:%M'),
                })
            context = {'schedule_data': json.dumps(new_schedule), 'success_message': 'Schedule saved successfully!'}
            response = render(request, 'coaching/partials/coach/_recurring_availability_form.html', context)
            response['HX-Trigger'] = 'recurring-schedule-updated'
            return response

        except (ValueError, TypeError) as e:
            return JsonResponse({"error": str(e)}, status=400)
        except Exception as e:
            return JsonResponse({"error": "An unexpected error occurred."}, status=500)

    # GET request
    schedule = [[] for _ in range(7)]
    for slot in RecurringAvailability.objects.filter(coach=coach).order_by('start_time'):
        schedule[slot.day_of_week].append({
            'start': slot.start_time.strftime('%H:%M'),
            'end': slot.end_time.strftime('%H:%M'),
        })

    context = {'schedule_data': json.dumps(schedule)}
    return render(request, 'coaching/partials/coach/_recurring_availability_form.html', context)


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
        
        return render(request, 'coaching/partials/coach/_specific_slots_list.html', {'specific_slots': slots})

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
    return render(request, 'coaching/partials/coach/add_availability_modal.html', context)


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
    # This view can be accessed by both coaches and clients, so we get the coach from the request.
    coach_id = request.GET.get('coach_id')
    coach = get_object_or_404(get_user_model(), pk=coach_id, is_coach=True)

    now = timezone.now()
    year = int(request.GET.get('year', now.year))
    month = int(request.GET.get('month', now.month))

    # Get offering and coach from request to determine slot duration
    try:
        offering_id = request.GET.get('offering_id')
        offering = get_object_or_404(CoachOffering, pk=offering_id)
    except (ValueError, CoachOffering.DoesNotExist):
        return HttpResponse("Invalid or missing Offering ID.", status=400)

    coach_tz_str = str(getattr(coach, 'user_timezone', timezone.get_current_timezone()))
    coach_tz = pytz.timezone(coach_tz_str)
    today = now.astimezone(coach_tz).date()
    current_month_obj, prev_month_obj, next_month_obj = get_nav_dates(year, month)
    prev_month_is_past = (prev_month_obj.year < today.year) or \
                         (prev_month_obj.year == today.year and prev_month_obj.month < today.month)
    user_tz_str = str(getattr(request.user, 'user_timezone', timezone.get_current_timezone()))
    user_tz = pytz.timezone(user_tz_str)

    final_grid = build_availability_grid(coach, offering, year, month, current_month_obj, today, user_tz, request.GET.get('start_date'), request.GET.get('end_date'))
    context = {
        'offering': offering,
        'coach': coach,
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
        'coaching/partials/booking/calendar_grid_fragment.html',
        context
    )
