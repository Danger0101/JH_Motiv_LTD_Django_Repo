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

from coaching_availability.utils import get_coach_available_slots 
from datetime import timedelta, date, datetime

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        summary = get_cart_summary_data(cart)
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
        user = self.request.user

        # 1. Initialize defaults to avoid template errors
        context['coach_upcoming_sessions'] = []
        context['coach_clients'] = []
        
        # 2. Cart & Marketing
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        preference, created = MarketingPreference.objects.get_or_create(user=user)
        context['marketing_preference'] = preference

        # 3. User's purchased offerings
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=user).order_by('-enrolled_on')

        # 4. Flags
        context['is_coach'] = getattr(user, 'is_coach', False)
        context['is_staff'] = user.is_staff
        context['google_calendar_connected'] = False

        # 5. Initialize Forms (for everyone, just in case)
        context['weekly_schedule_formset'] = None
        context['vacation_form'] = None
        context['override_form'] = None
        context['days_of_week'] = None

        # 6. COACH LOGIC
        if hasattr(user, 'coach_profile'):
            coach_profile = user.coach_profile
            
            # GCal Check
            try:
                context['google_calendar_connected'] = GoogleCredentials.objects.filter(coach=coach_profile).exists()
            except Exception:
                pass

            # Availability Forms
            WeeklyScheduleFormSet = modelformset_factory(
                CoachAvailability,
                form=WeeklyScheduleForm,
                extra=0,
                can_delete=True
            )
            queryset = CoachAvailability.objects.filter(coach=user).order_by('day_of_week')
            context['weekly_schedule_formset'] = WeeklyScheduleFormSet(queryset=queryset)
            context['vacation_form'] = CoachVacationForm()
            context['override_form'] = DateOverrideForm()
            context['days_of_week'] = CoachAvailability.DAYS_OF_WEEK

            # --- CRITICAL FIX: Fetch Sessions Correctly ---
            # Must use SessionBooking objects here
            context['coach_upcoming_sessions'] = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now(),
                status__in=['BOOKED', 'RESCHEDULED']
            ).select_related('client').order_by('start_datetime')

            # --- Fetch Clients Correctly ---
            User = get_user_model()
            enrollment_client_ids = ClientOfferingEnrollment.objects.filter(
                coach=coach_profile, 
                is_active=True
            ).values_list('client_id', flat=True)
            
            booking_client_ids = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now()
            ).values_list('client_id', flat=True)

            client_ids = set(list(enrollment_client_ids) + list(booking_client_ids))
            context['coach_clients'] = User.objects.filter(id__in=client_ids).distinct()

        # 7. Available Credits for Booking Tab
        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')
        
        context['active_tab'] = 'account' # Default tab
        
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
    return render(request, 'accounts/profile_offerings.html', {
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