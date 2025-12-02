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
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings

from .models import ClientOfferingEnrollment, SessionBooking
from accounts.models import CoachProfile
from coaching_availability.utils import get_coach_available_slots
from coaching_core.models import Offering, Workshop
from coaching_client.models import ContentPage
from cart.utils import get_or_create_cart, get_cart_summary_data

BOOKING_WINDOW_DAYS = 90

# --- EXISTING VIEWS (Preserved) ---

def coach_landing_view(request):
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
    return render(request, 'coaching_booking/coach_landing.html', context)

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

# --- UPDATED BOOKING & MANAGEMENT VIEWS ---

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')

    def htmx_error(msg):
        messages.error(request, msg)
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    if not all([enrollment_id, coach_id, start_time_str]):
        return htmx_error("Missing booking information. Please try again.")

    try:
        enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        
        try:
            start_datetime_naive = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
            start_datetime_obj = timezone.make_aware(start_datetime_naive)
        except ValueError:
            start_datetime_naive = datetime.fromisoformat(start_time_str)
            start_datetime_obj = timezone.make_aware(start_datetime_naive)

        now = timezone.now()

        if start_datetime_obj < now:
            return htmx_error("Cannot book a session in the past.")
        
        if start_datetime_obj > now + timedelta(days=BOOKING_WINDOW_DAYS):
            return htmx_error(f"Cannot book more than {BOOKING_WINDOW_DAYS} days in advance.")

        if enrollment.remaining_sessions <= 0:
            return htmx_error("No sessions remaining for this enrollment.")

        with transaction.atomic():
            session_length = enrollment.offering.session_length_minutes
            available_slots = get_coach_available_slots(
                coach_profile,
                start_datetime_obj.date(),
                start_datetime_obj.date(),
                session_length,
                offering_type='one_on_one'
            )
            
            is_available = False
            for slot in available_slots:
                slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                if slot_aware == start_datetime_obj:
                    is_available = True
                    break
            
            if not is_available:
                return htmx_error("That time slot is no longer available.")

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
        return htmx_error(f"An error occurred: {str(e)}")


@login_required
@require_POST
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    is_credit_restored = booking.cancel()
    
    if is_credit_restored:
        messages.success(request, "Session canceled successfully. Your credit has been restored.")
    else:
        messages.warning(request, "Session canceled. Because this was within 24 hours, the credit was forfeited per our Terms of Service.")
    
    # Fixed: Pass 'active_tab' context
    return render(request, 'accounts/profile_bookings.html', {'active_tab': 'canceled'})


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
        messages.error(request, "Please select a new time.")
    else:
        try:
            new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
            new_start_time = timezone.make_aware(new_start_time)

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
                messages.error(request, "That time slot is no longer available. Please choose another.")
            else:
                result = booking.reschedule(new_start_time)
                if result == 'LATE':
                    messages.error(request, "Sessions cannot be rescheduled within 24 hours of the start time.")
                else:
                    messages.success(request, f"Session successfully rescheduled to {new_start_time.strftime('%B %d, %H:%M')}.")

        except ValueError:
            messages.error(request, "Invalid date format.")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

    # Fixed: Pass 'active_tab' context
    return render(request, 'accounts/profile_bookings.html', {'active_tab': 'upcoming'})


@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).select_related('offering')

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
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    if not coach_id or not enrollment_id:
        return HttpResponse(
            '&lt;div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center h-full flex flex-col justify-center items-center"&gt;'
            '&lt;p class="text-gray-500 font-medium"&gt;Select an Offering and a Coach to view availability.&lt;/p&gt;'
            '&lt;/div&gt;'
        )

    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    date_obj = date(year, month, 1)
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

    context = {
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'selected_date': None,
        'available_slots': [],
        'error_message': None
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