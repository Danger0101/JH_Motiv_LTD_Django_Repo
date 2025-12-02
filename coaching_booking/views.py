from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta, datetime
import calendar
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from coaching_core.models import Offering, Workshop
from coaching_availability.utils import get_coach_available_slots
from coaching_client.models import ContentPage
from accounts.models import CoachProfile
from .models import ClientOfferingEnrollment, SessionBooking
from cart.utils import get_or_create_cart, get_cart_summary_data

BOOKING_WINDOW_DAYS = 90

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')

    # Helper to return error response via HTMX (often a redirect)
    def htmx_error_redirect(msg):
        messages.error(request, msg)
        response = HttpResponse(status=200) # Return 200 so HTMX processes the redirect
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    if not all([enrollment_id, coach_id, start_time_str]):
        return htmx_error_redirect("Missing booking information.")

    try:
        enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
        coach_profile = get_object_or_04(CoachProfile, id=coach_id)
        
        start_datetime_naive = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        start_datetime_obj = timezone.make_aware(start_datetime_naive)
        
        now = timezone.now()
        if start_datetime_obj < now:
            return htmx_error_redirect("Cannot book a session in the past.")
            
        if start_datetime_obj > now + timedelta(days=BOOKING_WINDOW_DAYS):
            return htmx_error_redirect(f"Cannot book more than {BOOKING_WINDOW_DAYS} days in advance.")

        if enrollment.remaining_sessions <= 0:
            return htmx_error_redirect("No sessions remaining for this enrollment.")

        with transaction.atomic():
            session_length_minutes = enrollment.offering.session_length_minutes
            requested_date = start_datetime_obj.date()
            
            truly_available_slots = get_coach_available_slots(
                coach_profile,
                requested_date,
                requested_date,
                session_length_minutes,
                offering_type='one_on_one'
            )
            
            is_available = False
            for slot in truly_available_slots:
                slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                if slot_aware == start_datetime_obj:
                    is_available = True
                    break

            if not is_available:
                return htmx_error_redirect("The selected slot is no longer available.")

            SessionBooking.objects.create(
                enrollment=enrollment,
                coach=coach_profile,
                client=request.user,
                start_datetime=start_datetime_obj,
            )
        
        messages.success(request, f"Session confirmed for {start_datetime_obj.strftime('%B %d, %Y at %I:%M %p')}.")
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    except Exception as e:
        return htmx_error_redirect(f"An error occurred: {e}")

@login_required
@require_POST
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    
    # Perform cancellation (returns True if refunded, False if forfeited)
    is_refunded = booking.cancel()
    
    if is_refunded:
        messages.success(request, "Session canceled successfully. Your credit has been restored.")
    else:
        messages.warning(request, "Session canceled. Credit forfeited (less than 24h notice).")
    
    # Refresh the list
    user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
    return render(request, 'accounts/profile_bookings.html', {'user_bookings': user_bookings})

@login_required
def reschedule_session_form(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    return render(request, 'accounts/partials/reschedule_form.html', {'booking': booking})

@login_required
@require_POST
def reschedule_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    new_start_time_str = request.POST.get('new_start_time')
    
    if not new_start_time_str:
        return HttpResponse("New start time is required.", status=400)
    
    try:
        new_start_naive = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
        new_start_time = timezone.make_aware(new_start_naive)
        
        # Check Limits
        now = timezone.now()
        if new_start_time < now:
            messages.error(request, "Cannot reschedule to the past.")
        elif new_start_time > now + timedelta(days=BOOKING_WINDOW_DAYS):
            messages.error(request, f"Cannot reschedule more than {BOOKING_WINDOW_DAYS} days out.")
        else:
            # Check availability for the new slot
            session_length = booking.enrollment.offering.session_length_minutes
            available_slots = get_coach_available_slots(
                booking.coach, new_start_time.date(), new_start_time.date(), session_length, 'one_on_one'
            )
            
            is_available = False
            for slot in available_slots:
                slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                if slot_aware == new_start_time:
                    is_available = True
                    break
            
            if not is_available:
                messages.error(request, "Selected slot is not available.")
            else:
                result = booking.reschedule(new_start_time)
                if result == 'LATE':
                    messages.error(request, "Cannot reschedule within 24 hours. Please cancel instead.")
                else:
                    messages.success(request, "Session rescheduled successfully.")

    except ValueError:
        messages.error(request, "Invalid date format.")
    except Exception as e:
        messages.error(request, f"Error: {e}")

    user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
    return render(request, 'accounts/profile_bookings.html', {'user_bookings': user_bookings})

def coach_landing_view(request):
    """Renders the coach landing page."""
    coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
    offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches')
    workshops = Workshop.objects.filter(active_status=True)
    knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]
    
    KNOWLEDGE_CATEGORIES = [('all', 'Business Coaches')]
    cart = get_or_create_cart(request)
    
    context = {
        'coaches': coaches,
        'offerings': offerings,
        'workshops': workshops,
        'knowledge_pages': knowledge_pages,
        'knowledge_categories': KNOWLEDGE_CATEGORIES[1:],
        'page_summary_text': "Welcome to our coaching services!",
        'summary': get_cart_summary_data(cart),
    }
    # FIXED: Return a proper HTTP response
    return render(request, 'coaching_booking/coach_landing.html', context)

# ... (keep OfferListView and OfferEnrollmentStartView as they were) ...
class OfferListView(ListView):
    model = Offering
    template_name = 'coaching_booking/offering_list.html'
    context_object_name = 'offerings'
    def get_queryset(self):
        return Offering.objects.filter(active_status=True)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

class OfferEnrollmentStartView(LoginRequiredMixin, DetailView):
    model = Offering
    template_name = 'coaching_booking/checkout_embedded.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['STRIPE_PUBLIC_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

@login_required
def profile_book_session_partial(request):
    """
    Renders the initial 'Book Session' tab content.
    """
    # Fetch active enrollments for the user
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).select_related('offering')

    # Fetch all available coaches
    coaches = CoachProfile.objects.filter(
        user__is_active=True,
        is_available_for_new_clients=True
    ).select_related('user')
    
    today = timezone.now().date()

    context = {
        'user_offerings': user_offerings,
        'coaches': coaches,
        'initial_year': today.year,
        'initial_month': today.month,
        'selected_enrollment_id': '', 
        'selected_coach_id': '',      
    }
    return render(request, 'coaching_booking/profile_book_session.html', context)

@login_required
def get_booking_calendar(request):
    """
    Returns the HTML for the calendar widget (HTMX).
    """
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    date_obj = date(year, month, 1)
    
    # Prev/Next logic
    prev_date = date_obj - timedelta(days=1)
    prev_month = prev_date.month
    prev_year = prev_date.year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    cal = calendar.Calendar(firstweekday=0)
    calendar_rows = cal.monthdayscalendar(year, month)
    
    today = timezone.now().date()
    max_date = today + timedelta(days=BOOKING_WINDOW_DAYS)

    context = {
        'calendar_rows': calendar_rows,
        'year': year,
        'month': month,
        'current_month_name': date_obj.strftime('%B'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'max_date': max_date,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)

@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    # Initialize context with IDs so template doesn't crash on KeyError
    context = {
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'selected_date': None,
        'error_message': None,
        'available_slots': []
    }

    if not all([date_str, coach_id, enrollment_id]):
        context['error_message'] = 'Please select an offering and a coach first.'
        return render(request, 'coaching_booking/partials/available_slots.html', context)

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        context['selected_date'] = selected_date
        
        now = timezone.now()
        max_date = now.date() + timedelta(days=BOOKING_WINDOW_DAYS)

        if selected_date < now.date():
            context['error_message'] = 'Cannot book dates in the past.'
            return render(request, 'coaching_booking/partials/available_slots.html', context)
        
        if selected_date > max_date:
            context['error_message'] = 'This date is too far in the future.'
            return render(request, 'coaching_booking/partials/available_slots.html', context)

        coach_profile = CoachProfile.objects.get(id=coach_id)
        enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
        session_length = enrollment.offering.session_length_minutes
        
        available_slots = get_coach_available_slots(
            coach_profile,
            selected_date,
            selected_date, 
            session_length,
            offering_type='one_on_one'
        )
        
        formatted_slots = []
        for slot in available_slots:
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            if slot_aware > now:
                formatted_slots.append({
                    'start_time': slot_aware,
                    'end_time': slot_aware + timedelta(minutes=session_length)
                })

        context['available_slots'] = formatted_slots

    except (ValueError, CoachProfile.DoesNotExist, ClientOfferingEnrollment.DoesNotExist):
        context['error_message'] = 'Invalid request data.'
    except Exception as e:
        context['error_message'] = f'Error fetching slots: {str(e)}'

    return render(request, 'coaching_booking/partials/available_slots.html', context)