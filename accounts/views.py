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
from accounts.models import CoachProfile # Assuming CoachProfile is in accounts.models or accessible
from gcal.models import GoogleCredentials
from coaching_availability.forms import DateOverrideForm, CoachVacationForm, WeeklyScheduleForm
from django.forms import modelformset_factory
from coaching_availability.models import CoachAvailability, CoachVacation, DateOverride
from django.db import transaction
from collections import defaultdict
from django.views import View
from django.contrib.auth import get_user_model # ADDED
from coaching_availability.utils import get_coach_available_slots # Import the new utility function
from datetime import timedelta, date, datetime

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    """
    Overrides the default allauth LoginView to handle HTMX requests correctly.
    When a login is successful via an HTMX request, it prevents the "page-in-page"
    effect by sending an HX-Redirect header, which tells HTMX to perform a full
    browser redirect.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        summary = get_cart_summary_data(cart)
        
        # Add this line to fix the template error
        context['ACCOUNT_ALLOW_REGISTRATION'] = getattr(settings, 'ACCOUNT_ALLOW_REGISTRATION', True) 
        return context

    def form_valid(self, form):
        # Let the parent class handle the login logic.
        response = super().form_valid(form)
        
        # If the request is from HTMX, replace the standard redirect with an HX-Redirect.
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

        # 1. Initialize defaults
        context['coach_upcoming_sessions'] = []
        context['coach_clients'] = []
        
        # 2. Standard Context (Cart, Marketing, etc.)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        preference, created = MarketingPreference.objects.get_or_create(user=user)
        context['marketing_preference'] = preference
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=user).order_by('-enrolled_on')
        
        context['is_coach'] = getattr(user, 'is_coach', False)
        context['is_staff'] = user.is_staff

        # 3. Coach Dashboard Logic
        context['google_calendar_connected'] = False
        
        if hasattr(user, 'coach_profile'):
            coach_profile = user.coach_profile
            
            # Check GCal Connection
            try:
                context['google_calendar_connected'] = GoogleCredentials.objects.filter(coach=coach_profile).exists()
            except Exception:
                pass

            # --- START ADDED SECTION: Availability Forms ---
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

            # --- START ADDED SECTION: Fetch Real Data ---
            
            # A. Fetch Upcoming Sessions
            context['coach_upcoming_sessions'] = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now(),
                status__in=['BOOKED', 'RESCHEDULED']
            ).select_related('client').order_by('start_datetime')

            # B. Fetch Active Clients (Unique users from enrollments or bookings)
            enrollment_client_ids = ClientOfferingEnrollment.objects.filter(
                coach=coach_profile, 
                is_active=True
            ).values_list('client_id', flat=True)
            
            booking_client_ids = SessionBooking.objects.filter(
                coach=coach_profile,
                start_datetime__gte=timezone.now()
            ).values_list('client_id', flat=True)

            client_ids = set(list(enrollment_client_ids) + list(booking_client_ids))
            User = get_user_model()
            context['coach_clients'] = User.objects.filter(id__in=client_ids).distinct()
            
            # --- END ADDED SECTION ---

        # 4. Book Session Data (Available credits)
        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')
        
        # Default tab
        context['active_tab'] = 'account' 
        
        return context



@login_required
def update_marketing_preference(request):
    """
    Handles HTMX POST request to update the user's marketing subscription status.
    Returns an HTML fragment to update the UI (required by HTMX).
    """
    if request.method == 'POST':
        # The 'is_subscribed' input is a checkbox; its presence means 'on'.
        # We assume the input name from the template below is 'is_subscribed'.
        is_subscribed = request.POST.get('is_subscribed') == 'on' 
        
        # Get or create the preference object
        preference, created = MarketingPreference.objects.get_or_create(user=request.user)
        preference.is_subscribed = is_subscribed
        preference.save()
        
        # Use a status fragment for HTMX to swap the UI dynamically
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
    """
    Handles rendering the content for the session booking tabs (Upcoming, Past, Canceled)
    with pagination. This view is intended to be called via HTMX.
    """
    now = timezone.now()
    active_tab = request.GET.get('tab', 'upcoming')

    bookings_qs = SessionBooking.objects.filter(client=request.user)

    if active_tab == 'upcoming':
        # Booked or Rescheduled sessions that are in the future
        bookings_list = bookings_qs.filter(
            status__in=['BOOKED', 'RESCHEDULED'],
            start_datetime__gte=now
        ).order_by('start_datetime')
    elif active_tab == 'past':
        # Completed sessions, or booked/rescheduled sessions that are now in the past
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

    paginator = Paginator(bookings_list, 10)  # 10 bookings per page
    page_number = request.GET.get('page')
    user_bookings_page = paginator.get_page(page_number)

    context = {
        'user_bookings_page': user_bookings_page,
        'active_tab': active_tab,
    }
    
    # This renders JUST the list and pagination controls into a partial
    return render(request, 'accounts/partials/_booking_list.html', context)

@login_required
def coach_clients_partial(request):
    """
    HTMX view to fetch the list of active clients for the coach.
    Includes clients explicitly assigned AND clients with upcoming bookings.
    """
    # Ensure user is a coach
    if not hasattr(request.user, 'coach_profile'):
        return HttpResponse("Unauthorized", status=401)

    coach_profile = request.user.coach_profile
    now = timezone.now()
    
    # 1. Enrollments explicitly assigned to this coach
    #    (Matches clients who bought a package specifically with you)
    direct_enrollments_query = Q(coach=coach_profile) & (
        Q(is_active=True) | 
        Q(expiration_date__gte=now)
    )

    # 2. Enrollments linked via upcoming sessions (Implied relationship)
    #    (Matches clients who booked you, even if the enrollment isn't assigned to you)
    session_enrollment_ids = SessionBooking.objects.filter(
        coach=coach_profile,
        start_datetime__gte=now,
        status__in=['BOOKED', 'RESCHEDULED'],
        enrollment__isnull=False
    ).values_list('enrollment_id', flat=True).distinct()

    implied_enrollments_query = Q(id__in=session_enrollment_ids) & Q(is_active=True)

    # Combine queries: Fetch Enrollments that match EITHER criteria
    client_enrollments_qs = ClientOfferingEnrollment.objects.filter(
        direct_enrollments_query | implied_enrollments_query
    ).distinct().select_related('client', 'offering').order_by('client__last_name')

    # Pagination
    paginator = Paginator(client_enrollments_qs, 10) 
    page_number = request.GET.get('page')
    coach_clients_page = paginator.get_page(page_number)

    context = {
        'coach_clients_page': coach_clients_page,
    }
    return render(request, 'accounts/partials/_coach_clients_list.html', context)

@login_required
def get_coaches_for_offering(request):
    enrollment_id_str = request.GET.get('enrollment_id')
    coaches_to_display = []
    
    html_options = '<option value="">-- Select a Coach --</option>'

    if enrollment_id_str:
        try:
            enrollment_id = int(enrollment_id_str)
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            
            # Prioritize coach assigned directly to the enrollment
            if enrollment.coach:
                coaches_to_display = [enrollment.coach]
            else:
                # Fallback to coaches associated with the offering
                coaches_to_display = enrollment.offering.coaches.filter(
                    user__is_active=True, 
                    is_available_for_new_clients=True
                ).distinct() # Use distinct to avoid duplicates if a coach is linked multiple ways
            
            for coach in coaches_to_display:
                html_options += f'<option value="{coach.id}">{coach.user.get_full_name() or coach.user.username}</option>'

        except (ValueError, ClientOfferingEnrollment.DoesNotExist) as e:
            # Log the error for debugging purposes
            print(f"ERROR in get_coaches_for_offering: {e}")
            # The default "Select a Coach" option will remain if an error occurs
    
    return HttpResponse(html_options)
