from django.conf import settings
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from .models import MarketingPreference
from allauth.account.views import LoginView, SignupView, PasswordResetView, PasswordChangeView, PasswordSetView, LogoutView, PasswordResetDoneView, PasswordResetDoneView
from cart.utils import get_or_create_cart, get_cart_summary_data
from coaching_booking.models import ClientOfferingEnrollment, SessionBooking
from coaching_core.models import Offering
from accounts.models import CoachProfile 
from gcal.models import GoogleCredentials
from coaching_availability.forms import DateOverrideForm, CoachVacationForm, WeeklyScheduleForm
from django.forms import modelformset_factory
from coaching_availability.models import CoachAvailability, CoachVacation, DateOverride
from django.db import transaction
from collections import defaultdict
from django.views import View
from django.contrib.auth import get_user_model
from datetime import timedelta, date, datetime

# --- FIX IMPORTS HERE ---
try:
    from dreamers.models import Dreamer
except ImportError:
    Dreamer = None

try:
    from products.models import StockItem
except ImportError:
    StockItem = None

try:
    from payments.models import Order
except ImportError:
    Order = None
# ------------------------

from coaching_availability.utils import get_coach_available_slots 


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        context['ACCOUNT_ALLOW_REGISTRATION'] = getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True) 
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.htmx:
            return HttpResponse(status=204, headers={'HX-Redirect': response.url})
        return response

class CustomSignupView(SignupView):
    template_name = 'accounts/signup.html'

class CustomPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset.html'

class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'

class CustomPasswordSetView(PasswordSetView):
    template_name = 'accounts/password_set.html'

class CustomLogoutView(LogoutView):
    template_name = 'accounts/logout.html'

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # --- COACHING DASHBOARD DATA ---
        context['coach_upcoming_sessions'] = []
        if hasattr(self.request.user, 'coach_profile'):
            coach_profile = self.request.user.coach_profile
            context['coach_upcoming_sessions'] = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now(),
                status__in=['BOOKED', 'RESCHEDULED']
            ).select_related('client').order_by('start_datetime')

        # Initialized as empty; loaded via HTMX
        context['coach_clients'] = []
        
        # --- STAFF DASHBOARD DATA ---
        context['is_staff'] = self.request.user.is_staff
        if self.request.user.is_staff:
            # 1. Recent Orders (Sales Pulse)
            if Order:
                # FIX: Changed '-created' to '-created_at' to match Order model
                context['staff_recent_orders'] = Order.objects.select_related('user').order_by('-created_at')[:5]
            
            # 2. Low Stock Alerts (Inventory Risk)
            if StockItem:
                context['staff_low_stock'] = StockItem.objects.filter(quantity__lt=5).select_related('variant__product', 'pool')[:5]
            
            # 3. Community Stats
            if Dreamer:
                context['staff_dreamer_count'] = Dreamer.objects.count()

        # --- EXISTING CONTEXT ---
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        
        preference, created = MarketingPreference.objects.get_or_create(user=self.request.user)
        context['marketing_preference'] = preference
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=self.request.user).order_by('-enrolled_on')

        context['is_coach'] = self.request.user.is_coach
        
        google_calendar_connected = False
        if self.request.user.is_coach:
            try:
                if hasattr(self.request.user, 'coach_profile'):
                    google_calendar_connected = GoogleCredentials.objects.filter(coach=self.request.user.coach_profile).exists()
            except Exception:
                pass 
        context['google_calendar_connected'] = google_calendar_connected

        context['weekly_schedule_formset'] = None
        context['vacation_form'] = None
        context['override_form'] = None
        context['days_of_week'] = None

        if hasattr(self.request.user, 'coach_profile'):
            coach_profile = self.request.user.coach_profile
            WeeklyScheduleFormSet = modelformset_factory(
                CoachAvailability,
                form=WeeklyScheduleForm,
                extra=0,
                can_delete=True
            )
            queryset = CoachAvailability.objects.filter(coach=self.request.user).order_by('day_of_week')
            context['weekly_schedule_formset'] = WeeklyScheduleFormSet(queryset=queryset)
            context['vacation_form'] = CoachVacationForm()
            context['override_form'] = DateOverrideForm()
            context['days_of_week'] = CoachAvailability.DAYS_OF_WEEK

        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=self.request.user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')
        
        context['active_tab'] = 'account'
        return context

@login_required
def update_marketing_preference(request):
    if request.method == 'POST':
        is_subscribed = request.POST.get('is_subscribed') == 'on' 
        preference, created = MarketingPreference.objects.get_or_create(user=request.user)
        preference.is_subscribed = is_subscribed
        preference.save()
        return render(request, 'accounts/partials/marketing_status_fragment.html', 
                      {'marketing_preference': preference})
    return HttpResponse("Invalid request", status=400)

# HTMX Profile Views
@login_required
def profile_offerings_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(client=request.user).order_by('-enrolled_on')
    available_credits = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now().date()
    ).order_by('-enrolled_on')
    return render(request, 'accounts/partials/profile_offerings_list.html', {
        'user_offerings': user_offerings,
        'available_credits': available_credits,
        'active_tab': 'offerings'
    })

@login_required
def profile_bookings_partial(request):
    now = timezone.now()
    active_tab = request.GET.get('tab', 'upcoming')
    bookings_qs = SessionBooking.objects.filter(client=request.user)

    if active_tab == 'upcoming':
        bookings_list = bookings_qs.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now
        ).order_by('start_datetime')
    elif active_tab == 'past':
        bookings_list = bookings_qs.filter(
            Q(status='COMPLETED') |
            Q(status__in=['BOOKED', 'RESCHEDULED'], start_datetime__lt=now)
        ).order_by('-start_datetime')
    elif active_tab == 'canceled':
        bookings_list = bookings_qs.filter(status='CANCELED').order_by('-start_datetime')
    else:
        active_tab = 'upcoming'
        bookings_list = bookings_qs.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now
        ).order_by('start_datetime')

    paginator = Paginator(bookings_list, 10)
    page_number = request.GET.get('page')
    user_bookings_page = paginator.get_page(page_number)

    context = {
        'user_bookings_page': user_bookings_page,
        'active_tab': active_tab,
    }
    return render(request, 'accounts/partials/_booking_list.html', context)

@login_required
def get_coaches_for_offering(request):
    enrollment_id_str = request.GET.get('enrollment_id')
    html_options = '<option value="">-- Select a Coach --</option>'

    if enrollment_id_str:
        try:
            enrollment_id = int(enrollment_id_str)
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            
            if enrollment.coach:
                coaches_to_display = [enrollment.coach]
            else:
                coaches_to_display = enrollment.offering.coaches.filter(
                    user__is_active=True, 
                    is_available_for_new_clients=True
                ).distinct()
            
            for coach in coaches_to_display:
                html_options += f'<option value="{coach.id}">{coach.user.get_full_name() or coach.user.username}</option>'

        except (ValueError, ClientOfferingEnrollment.DoesNotExist):
            pass
    
    return HttpResponse(html_options)

@login_required
def coach_clients_partial(request):
    # Ensure user is a coach
    if not hasattr(request.user, 'coach_profile'):
        return HttpResponse("Unauthorized", status=401)

    coach_profile = request.user.coach_profile
    now = timezone.now()
    
    # 1. Enrollments explicitly assigned to this coach
    direct_query = Q(coach=coach_profile) & (
        Q(is_active=True) | 
        Q(expiration_date__gte=now)
    )

    # 2. Enrollments linked via upcoming sessions
    session_enrollment_ids = SessionBooking.objects.filter(
        coach=coach_profile,
        start_datetime__gte=now,
        status__in=['BOOKED', 'RESCHEDULED'],
        enrollment__isnull=False
    ).values_list('enrollment_id', flat=True).distinct()

    implied_query = Q(id__in=session_enrollment_ids) & Q(is_active=True)

    # Combine queries
    client_enrollments_qs = ClientOfferingEnrollment.objects.filter(
        direct_query | implied_query
    ).distinct().select_related('client', 'offering').order_by('client__last_name')

    # Pagination
    paginator = Paginator(client_enrollments_qs, 10) 
    page_number = request.GET.get('page')
    coach_clients_page = paginator.get_page(page_number)

    context = {
        'coach_clients_page': coach_clients_page,
    }
    return render(request, 'accounts/partials/_coach_clients_list.html', context)
