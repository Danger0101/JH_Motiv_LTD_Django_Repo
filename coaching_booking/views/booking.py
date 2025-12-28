from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, date, timedelta
import json
import logging
from django.http import HttpResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.exceptions import ValidationError
from django.db import transaction
import pytz

from ..models import SessionBooking, ClientOfferingEnrollment, OneSessionFreeOffer
from accounts.models import CoachProfile
from ..services import BookingService, BookingPermissions
from ..utils import htmx_error, BOOKING_WINDOW_DAYS

logger = logging.getLogger(__name__)

@login_required
def profile_book_session(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(client=request.user, is_active=True, remaining_sessions__gt=0).select_related('offering', 'coach__user')
    free_offers = OneSessionFreeOffer.objects.filter(client=request.user, status='APPROVED').select_related('coach__user')
    coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
    
    reschedule_id = request.GET.get('reschedule_booking_id')
    booking = None
    if reschedule_id:
        booking = get_object_or_404(SessionBooking, id=reschedule_id, client=request.user)

    context = {
        'user_offerings': user_offerings,
        'free_offers': free_offers,
        'coaches': coaches,
        'selected_enrollment_id': request.GET.get('enrollment_id'),
        'selected_free_offer_id': request.GET.get('free_offer_id'),
        'reschedule_booking_id': reschedule_id,
        'booking': booking,
        'initial_year': timezone.now().year,
        'initial_month': timezone.now().month,
    }
    return render(request, 'coaching_booking/profile_book_session.html', context)

@login_required
def get_booking_calendar(request):
    enrollment_id = request.GET.get('enrollment_id')
    reschedule_booking_id = request.GET.get('reschedule_booking_id')
    coach_id = request.GET.get('coach_id')
    slot_target_id = request.GET.get('slot_target_id', '#time-slots-column')
    
    session_length = 60
    coach = None

    if coach_id:
        try: coach = CoachProfile.objects.get(id=coach_id)
        except CoachProfile.DoesNotExist: pass

    if reschedule_booking_id:
        try:
            booking = SessionBooking.objects.get(id=reschedule_booking_id, client=request.user)
            session_length = booking.get_duration_minutes() or 60
            if not coach: coach = booking.coach
        except SessionBooking.DoesNotExist: pass
    elif enrollment_id:
        if str(enrollment_id).startswith('free_'):
            try:
                offer = OneSessionFreeOffer.objects.get(id=str(enrollment_id).replace('free_', ''), client=request.user)
                if not coach: coach = offer.coach
                if offer.offering: session_length = offer.offering.session_length_minutes
            except: pass
        else:
            try:
                enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
                if not coach: coach = enrollment.coach or enrollment.offering.coaches.first()
                session_length = enrollment.offering.session_length_minutes
            except: pass

    if not coach:
        return HttpResponse('<div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center"><p class="text-gray-500">Select an Offering and a Coach.</p></div>')

    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year, month = timezone.now().year, timezone.now().month

    user_tz = request.COOKIES.get('USER_TIMEZONE', 'UTC')
    calendar_data = BookingService.get_month_schedule(coach, year, month, user_tz, session_length, exclude_booking_id=reschedule_booking_id)
    calendar_rows = [calendar_data[i:i+7] for i in range(0, len(calendar_data), 7)]

    current_date = date(year, month, 1)
    prev_date = current_date - timedelta(days=1)
    next_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    context = {
        'calendar_rows': calendar_rows,
        'current_year': year, 'current_month': month, 'current_month_name': current_date.strftime('%B'),
        'prev_month': prev_date.month, 'prev_year': prev_date.year,
        'next_month': next_date.month, 'next_year': next_date.year,
        'enrollment_id': enrollment_id, 'coach': coach,
        'reschedule_booking_id': reschedule_booking_id, 'slot_target_id': slot_target_id,
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)

@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    if not date_str: return HttpResponse('')
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        coach_profile = None
        session_length = 60
        
        reschedule_id = request.GET.get('reschedule_booking_id')
        enrollment_id = request.GET.get('enrollment_id')
        coach_id = request.GET.get('coach_id')
        free_offer_id = None

        if reschedule_id:
            booking = get_object_or_404(SessionBooking, id=reschedule_id, client=request.user)
            coach_profile = booking.coach
            session_length = booking.get_duration_minutes() or 60
        elif enrollment_id and str(enrollment_id).startswith('free_'):
            free_offer_id = str(enrollment_id).split('_')[1]
            offer = OneSessionFreeOffer.objects.get(id=free_offer_id, client=request.user)
            coach_profile = offer.coach
            enrollment_id = None # Clear to prevent confusion in template
        elif enrollment_id:
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            coach_profile = enrollment.coach or enrollment.offering.coaches.first()
            session_length = enrollment.offering.session_length_minutes
        elif coach_id:
            coach_profile = CoachProfile.objects.get(id=coach_id)

        if not coach_profile: return HttpResponse('<div class="text-red-500 text-sm">Coach not found.</div>')

        available_slots = BookingService.get_slots_for_coach(coach_profile, selected_date, session_length, exclude_booking_id=reschedule_id)
        user_tz = pytz.timezone(request.session.get('django_timezone', 'UTC'))
        formatted_slots = [{'iso_format': (s if timezone.is_aware(s) else timezone.make_aware(s)).isoformat(), 'label': (s if timezone.is_aware(s) else timezone.make_aware(s)).astimezone(user_tz).strftime('%I:%M %p')} for s in available_slots if (s if timezone.is_aware(s) else timezone.make_aware(s)) > timezone.now()]

        return render(request, 'coaching_booking/partials/_day_slots.html', {
            'slots': formatted_slots, 
            'selected_date': selected_date, 
            'enrollment_id': enrollment_id, 
            'free_offer_id': free_offer_id,
            'reschedule_booking_id': reschedule_id, 
            'coach': coach_profile
        })
    except Exception as e:
        return HttpResponse(f'<div class="text-red-500 text-sm">Error: {str(e)}</div>')

@login_required
def confirm_booking_modal(request):
    context = {
        'slot_iso': request.GET.get('time'),
        'enrollment_id': request.GET.get('enrollment_id'),
        'workshop_id': request.GET.get('workshop_id'),
        'reschedule_booking_id': request.GET.get('reschedule_booking_id'),
        'coach_id': request.GET.get('coach_id'),
    }

    # Determine POST URL for the form
    if context['reschedule_booking_id']:
        context['post_url'] = reverse('coaching_booking:reschedule_session', args=[context['reschedule_booking_id']])
    else:
        context['post_url'] = reverse('coaching_booking:book_session')

    # Restore UI Context Helpers
    if context['slot_iso']:
        try:
            clean_time = context['slot_iso'].replace('Z', '+00:00').replace(' ', '+')
            dt = datetime.fromisoformat(clean_time)
            context['pretty_time'] = dt.strftime('%B %d, %I:%M %p')
            context['slot_iso'] = clean_time
        except ValueError: pass

    if context['coach_id']:
        try:
            coach = CoachProfile.objects.select_related('user').get(id=context['coach_id'])
            context['coach_name'] = coach.user.get_full_name()
        except: pass

    if context['enrollment_id']:
        if str(context['enrollment_id']).startswith('free_'):
            context['offering_name'] = "Free Taster Session"
        else:
            try:
                enrollment = ClientOfferingEnrollment.objects.select_related('offering').get(id=context['enrollment_id'])
                context['offering_name'] = enrollment.offering.name
            except: pass
    elif context['reschedule_booking_id']:
        try:
            booking = SessionBooking.objects.select_related('offering').get(id=context['reschedule_booking_id'])
            if booking.offering: context['offering_name'] = booking.offering.name
        except: pass

    return render(request, 'coaching_booking/partials/booking_form.html', context)

@login_required
@require_POST
def book_session(request):
    try:
        booking_data = {
            'enrollment_id': request.POST.get('enrollment_id'),
            'free_offer_id': request.POST.get('free_offer_id'),
            'coach_id': request.POST.get('coach_id'),
            'workshop_id': request.POST.get('workshop_id'),
            'start_time': request.POST.get('start_time'),
            'email': request.POST.get('email'),
            'name': request.POST.get('name'),
        }
        result = BookingService.create_booking(booking_data, user=request.user)
        
        if result['type'] == 'confirmed':
            msg = f"Session confirmed for {result['booking'].start_datetime.strftime('%B %d, %Y at %I:%M %p')}."
            messages.success(request, msg)
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('accounts:account_profile')
            return response
        elif result['type'] == 'checkout':
            response = HttpResponse(status=204)
            response['HX-Redirect'] = result['url']
            return response
    except ValidationError as e:
        return htmx_error(str(e.message))
    except Exception as e:
        logger.error(f"Booking Error: {e}", exc_info=True)
        return htmx_error(f"An error occurred: {str(e)}")

@login_required
@require_POST
def reschedule_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if not BookingPermissions.can_manage_booking(request.user, booking):
        return htmx_error("Unauthorized.")
    if booking.status == 'CANCELED':
        return htmx_error("Cannot reschedule a canceled session.")

    try:
        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
        BookingService.reschedule_booking(
            booking, 
            request.POST.get('new_start_time') or request.POST.get('start_time'), 
            request.POST.get('coach_id'), 
            requesting_user=request.user,
            dashboard_url=dashboard_url
        )
        msg = f"Session rescheduled to {booking.start_datetime.strftime('%B %d, %H:%M')}."
        messages.success(request, msg)
        
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response
    except ValidationError as e:
        return htmx_error(e.messages[0] if hasattr(e, 'messages') else str(e))
    except Exception as e:
        logger.error(f"Reschedule Error: {e}", exc_info=True)
        return htmx_error("An unexpected error occurred.")

@login_required
@require_POST
@transaction.atomic
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if not BookingPermissions.can_manage_booking(request.user, booking):
        return htmx_error("Unauthorized.")

    dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
    is_refunded = BookingService.cancel_booking(booking, actor=request.user, dashboard_url=dashboard_url)
    
    msg = "Session canceled."
    toast_type = "success"
    if booking.client == request.user:
        if is_refunded: msg += " Credit restored."
        else: 
            msg += " Credit forfeited (late cancellation)."
            toast_type = "warning"
            messages.warning(request, msg)
    else:
        messages.success(request, msg)

    if request.headers.get('HX-Request'):
        response = HttpResponse(status=204)
        response['HX-Trigger'] = json.dumps({'closeModal': True, 'refreshBookings': True, 'showToast': {'message': msg, 'type': 'success'}})
        return response
    return redirect('accounts:account_profile')

@login_required
def request_coverage_modal(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if booking.coach != request.user.coach_profile:
        return HttpResponseForbidden("Unauthorized.")
    return render(request, 'coaching_booking/partials/request_coverage_modal.html', {'booking': booking})

@login_required
@require_POST
def create_coverage_request(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if booking.coach != request.user.coach_profile:
        return HttpResponseForbidden("Unauthorized.")
    try:
        BookingService.request_session_coverage(booking, request.user.coach_profile, request.POST.get('note', ''))
        messages.success(request, "Coverage request broadcasted.")
    except Exception as e:
        messages.error(request, str(e))
    return redirect('accounts:account_profile')

@login_required
def accept_coverage_view(request, request_id):
    if not hasattr(request.user, 'coach_profile'):
        messages.error(request, "Only coaches can perform this action.")
        return redirect('accounts:account_profile')
    success, message = BookingService.accept_session_coverage(request_id, request.user.coach_profile)
    if success: messages.success(request, message)
    else: messages.error(request, message)
    return redirect('accounts:account_profile')