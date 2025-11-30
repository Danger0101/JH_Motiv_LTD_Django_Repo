# accounts/views.py (Updated)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
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

from coaching_availability.utils import get_coach_available_slots # Import the new utility function
from datetime import timedelta, date, datetime
import calendar # Import timedelta and date

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
        context['summary'] = summary
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

        # Initialize coach-specific context variables to prevent KeyErrors for non-coaches
        context['coach_upcoming_sessions'] = []
        context['coach_clients'] = []
        
        cart = get_or_create_cart(self.request)
        summary = get_cart_summary_data(cart)
        context['summary'] = summary
        
        # Fetch marketing preferences
        preference, created = MarketingPreference.objects.get_or_create(user=self.request.user)
        context['marketing_preference'] = preference

        # Fetch user's coaching offerings (enrollments)
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=self.request.user).order_by('-enrolled_on')

        # Fetch user's upcoming and past booked sessions as a client
        now = timezone.now()
        context['client_upcoming_sessions'] = SessionBooking.objects.filter(
            client=self.request.user,
            start_datetime__gte=now
        ).order_by('start_datetime')
        context['client_past_sessions'] = SessionBooking.objects.filter(
            client=self.request.user,
            start_datetime__lt=now
        ).order_by('-start_datetime') # Order past sessions by most recent first

        # Add flags for dashboard elements
        context['is_coach'] = self.request.user.is_coach
        context['is_staff'] = self.request.user.is_staff

        google_calendar_connected = False
        if self.request.user.is_coach:
            try:
                coach_profile = self.request.user.coach_profile
                google_calendar_connected = GoogleCredentials.objects.filter(coach=coach_profile).exists()
            except CoachProfile.DoesNotExist:
                pass  # Coach profile doesn't exist, so no connection
        context['google_calendar_connected'] = google_calendar_connected

        user = self.request.user
        
        # Initialize coach-specific context variables for all users
        context['weekly_schedule_formset'] = None
        context['vacation_form'] = None
        context['override_form'] = None
        context['days_of_week'] = None

        # Only load coach data if the user is a coach
        if hasattr(user, 'coach_profile'):
            coach_profile = user.coach_profile
            
            # 1. Create the FormSet Class
            WeeklyScheduleFormSet = modelformset_factory(
                CoachAvailability,
                form=WeeklyScheduleForm,
                extra=0,
                can_delete=True
            )
            
            # 2. Create the QuerySet
            queryset = CoachAvailability.objects.filter(coach=user).order_by('day_of_week')
            
            # 3. Instantiate and Add to Context
            context['weekly_schedule_formset'] = WeeklyScheduleFormSet(queryset=queryset)
            
            # 4. Add other forms
            context['vacation_form'] = CoachVacationForm()
            context['override_form'] = DateOverrideForm()
            
            # 5. Add Days of Week (from Model)
            context['days_of_week'] = CoachAvailability.DAYS_OF_WEEK


        # For now, available_credits will be the same as user_offerings for simplicity
        # In a real scenario, this might be a separate model or a filtered queryset of enrollments
        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=self.request.user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')
        
        context['active_tab'] = 'integrations' # Set default active tab
        
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
    user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
    return render(request, 'accounts/profile_bookings.html', {
        'user_bookings': user_bookings,
        'active_tab': 'bookings'
    })

@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).order_by('-enrolled_on')
    coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True) # Filter active and available coaches
    
    selected_enrollment_id = request.GET.get('enrollment_id')
    selected_enrollment = None
    if selected_enrollment_id:
        selected_enrollment = get_object_or_404(ClientOfferingEnrollment, id=selected_enrollment_id, client=request.user)

    selected_coach_id = request.GET.get('coach_id')
    selected_coach = None
    if selected_coach_id:
        selected_coach = get_object_or_404(CoachProfile, id=selected_coach_id)

    # Initialize year and month for the calendar
    today = date.today()
    initial_year = today.year
    initial_month = today.month

    return render(request, 'accounts/profile_book_session.html', {
        'user_offerings': user_offerings,
        'coaches': coaches,
        'selected_enrollment': selected_enrollment,
        'selected_coach': selected_coach,
        'active_tab': 'book_session',
        'initial_year': initial_year,
        'initial_month': initial_month,
    })

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

@login_required
def get_available_slots(request):
    enrollment_id_str = request.GET.get('enrollment_id')
    coach_id_str = request.GET.get('coach_id')
    
    available_slots_data = []
    error_message = None

    print(f"DEBUG: get_available_slots called with enrollment_id_str='{enrollment_id_str}', coach_id_str='{coach_id_str}'")

    if not enrollment_id_str:
        error_message = "Please select an offering first."
        print(f"ERROR: {error_message}")
    elif not coach_id_str:
        error_message = "Please select a coach first."
        print(f"ERROR: {error_message}")
    else:
        try:
            enrollment_id = int(enrollment_id_str)
            coach_id = int(coach_id_str)

            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            coach_profile = CoachProfile.objects.get(id=coach_id)
            offering = enrollment.offering
            
            session_length_minutes = offering.session_length_minutes

            print(f"DEBUG: Offering session length: {session_length_minutes} minutes")

            if session_length_minutes <= 0:
                error_message = "Session length for the selected offering is invalid."
                print(f"ERROR: {error_message}")
            else:
                # Define the date range for availability checking
                today = date.today()
                start_date_param = request.GET.get('start_date')
                end_date_param = request.GET.get('end_date')

                if start_date_param:
                    start_date = datetime.strptime(start_date_param, '%Y-%m-%d').date()
                else:
                    start_date = today
                
                if end_date_param:
                    end_date = datetime.strptime(end_date_param, '%Y-%m-%d').date()
                else:
                    end_date = today + timedelta(days=30)
                
                print(f"DEBUG: Checking availability from {start_date} to {end_date}")

                generated_slots = get_coach_available_slots(
                    coach_profile,
                    start_date,
                    end_date,
                    session_length_minutes,
                    offering_type='one_on_one'
                )

                print(f"DEBUG: Generated {len(generated_slots)} slots.")

                for slot_start_datetime in generated_slots:
                    slot_end_datetime = slot_start_datetime + timedelta(minutes=session_length_minutes)
                    available_slots_data.append({
                        'start_time': slot_start_datetime,
                        'end_time': slot_end_datetime,
                    })

                if not available_slots_data:
                    error_message = "No available slots found for the selected criteria. Please check coach's availability."

        except ValueError as e:
            error_message = f"Invalid ID format: {e}"
            print(f"ERROR: {error_message}")
        except ClientOfferingEnrollment.DoesNotExist:
            error_message = "Selected offering enrollment not found."
            print(f"ERROR: {error_message} (ID: {enrollment_id_str})")
        except CoachProfile.DoesNotExist:
            error_message = "Selected coach not found."
            print(f"ERROR: {error_message} (ID: {coach_id_str})")
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            print(f"ERROR: {error_message}")

    return render(request, 'accounts/partials/available_slots.html', {
        'available_slots': available_slots_data,
        'error_message': error_message
    })

@login_required
def get_booking_calendar(request):
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    cal = calendar.Calendar(firstweekday=0) # Monday is 0
    # The `monthdayscalendar` method returns a list of lists of integers
    # where each integer is a day of the month or 0 for days outside the month.
    calendar_rows = cal.monthdayscalendar(year, month)

    today = date.today()

    # Calculate previous and next month/year for navigation
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    next_month_date = date(year, month, 1) + timedelta(days=32) # Go beyond to ensure next month

    context = {
        'year': year,
        'month': month,
        'current_month_name': date(year, month, 1).strftime('%B'), # Renamed from month_name
        'calendar_rows': calendar_rows, # Renamed from month_days
        'today': today,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'prev_month': prev_month_date.month,
        'prev_year': prev_month_date.year,
        'next_month': next_month_date.month,
        'next_year': next_month_date.year,
        'date': date, # Pass the date constructor for template logic
    }
    return render(request, 'accounts/partials/_calendar_widget.html', context)

@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    coach_id_str = request.GET.get('coach_id')
    enrollment_id_str = request.GET.get('enrollment_id')

    daily_slots_data = []
    error_message = None

    if not date_str or not coach_id_str or not enrollment_id_str:
        error_message = "Missing date, coach_id, or enrollment_id."
        return render(request, 'accounts/partials/_day_slots.html', {
            'daily_slots': daily_slots_data,
            'error_message': error_message
        })
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        coach_id = int(coach_id_str)
        enrollment_id = int(enrollment_id_str)

        coach_profile = CoachProfile.objects.get(id=coach_id)
        enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
        offering = enrollment.offering
        session_length_minutes = offering.session_length_minutes

        if session_length_minutes <= 0:
            error_message = "Session length for the selected offering is invalid."
        else:
            # Optimize to check only for the specific date
            generated_slots = calculate_bookable_slots(
                coach_profile,
                selected_date,
                selected_date, # Start and end date are the same for daily slots
                session_length_minutes,
                offering_type='one_on_one' # Assuming this is always one_on_one for now
            )

            for slot_start_datetime in generated_slots:
                slot_end_datetime = slot_start_datetime + timedelta(minutes=session_length_minutes)
                daily_slots_data.append({
                    'start_time': slot_start_datetime,
                    'end_time': slot_end_datetime,
                })
            
            if not daily_slots_data:
                error_message = "No available slots for this day."

    except ValueError as e:
        error_message = f"Invalid ID format or date format: {e}"
    except ClientOfferingEnrollment.DoesNotExist:
        error_message = "Selected offering enrollment not found."
    except CoachProfile.DoesNotExist:
        error_message = "Selected coach not found."
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"

    return render(request, 'accounts/partials/_day_slots.html', {
        'daily_slots': daily_slots_data,
        'error_message': error_message,
        'selected_date': selected_date if 'selected_date' in locals() else None,
        'coach_id': coach_id_str,
        'enrollment_id': enrollment_id_str,
    })
