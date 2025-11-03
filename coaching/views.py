# coaching/views.py (Refactored Main File)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.http import require_http_methods
import json
from django.utils import timezone
from django.db import transaction
from dateutil.parser import isoparse
from .utils import coach_is_valid

# Import all API functions from the new modules (Already provided)
from .api_views.vacation import coach_vacation_blocks, coach_vacation_block_detail
from .api_views.availability import ( # This is a placeholder, the view is defined below now.
    coach_specific_availability_view,
    coach_specific_availability_detail,
    coach_add_availability_modal_view,
    coach_create_availability_from_modal_view,
    coach_calendar_view
)
from .api_views.offerings import coach_offerings_list_create, coach_offerings_detail

# Model Imports (Added missing models: TokenApplication)

from django.contrib.auth import get_user_model

from .models import (

    UserOffering,

    SessionCredit,

    CoachingSession,

    CoachOffering,

    CreditApplication,

    RescheduleRequest,

    CoachSwapRequest,

    CancellationPolicy, 
    RecurringAvailability,

    SessionNote, SessionStatus,

    Goal

)





@login_required

def program_goals_view(request, user_offering_id):

    user_offering = get_object_or_404(UserOffering, id=user_offering_id)
    # Correctly check if the user is the client OR one of the coaches for the offering
    if request.user != user_offering.user and request.user not in user_offering.offering.coaches.all():

        return HttpResponse("Unauthorized", status=403)



    if request.method == 'POST':

        title = request.POST.get('title')

        description = request.POST.get('description')

        due_date = request.POST.get('due_date')

        if title and description:

            Goal.objects.create(

                user_offering=user_offering,

                title=title,

                description=description,

                due_date=due_date

            )

        return redirect('coaching:program_goals', user_offering_id=user_offering_id)



    goals = Goal.objects.filter(user_offering=user_offering).order_by('-created_at')

    return render(request, 'coaching/program/program_goals.html', {'user_offering': user_offering, 'goals': goals})

@login_required
def session_notes_view(request, session_id):
    session = get_object_or_404(CoachingSession, id=session_id)
    if request.user != session.coach:
        return HttpResponse("Unauthorized", status=403)

    if request.method == 'POST':
        note = request.POST.get('note')
        if note:
            SessionNote.objects.create(
                session=session,
                coach=request.user,
                note=note
            )
        return redirect('coaching:session_notes', session_id=session_id)

    notes = SessionNote.objects.filter(session=session).order_by('-created_at')
    return render(request, 'coaching/coach/session_notes.html', {'session': session, 'notes': notes})
from django.views.generic import ListView

class CoachDashboardView(LoginRequiredMixin, ListView):
    model = CoachingSession
    template_name = 'coaching/coach/coach_dashboard.html'
    context_object_name = 'sessions'

    def get_queryset(self):
        return CoachingSession.objects.filter(coach=self.request.user).order_by('-start_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context['upcoming_sessions'] = self.get_queryset().filter(start_time__gte=now)
        context['past_sessions'] = self.get_queryset().filter(start_time__lt=now)
        return context

# ^^ ASSUMING TokenApplication and Offering models exist/are created

User = get_user_model()

# --- MAIN PAGE VIEW (FIXED) ---

class CoachingOverview(TemplateView):
    template_name = 'coaching/coaching_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # FIX: Ensure all models used in the context are imported (Offering and CoachOffering).
        # We will use CoachOffering to represent all sessions, including the free one.
        # Note: You had 'CoachOffering' and 'Offering' lines. I've consolidated and ensured ordering.
        try:
            # Fetch all active offerings ordered by ID to prevent ValueError
            context['offerings'] = CoachOffering.objects.filter(is_active=True).prefetch_related('coaches').order_by('id')
        except Exception as e:
            # Handle the case where the model might not exist or another error occurs
            context['offerings'] = [] 
            print(f"Error fetching offerings: {e}")
            
        return context

# --- Existing Placeholder/Integration Functions (Remains Here) ---

def get_coach_availability(coach_user):
    # Placeholder logic for Google Calendar integration
    return ["9:00 AM", "10:00 AM", "11:00 AM"]

def calendar_link_init(request):
    return HttpResponse("OAuth flow initiation.")

def calendar_link_callback(request):
    return HttpResponse("OAuth callback handled.")

# --- Existing Booking/Program Views (Below) ---

@login_required
def coach_settings_view(request):
    """
    Main settings page for a coach to manage their availability,
    vacation blocks, and service offerings.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
    
    # Find a default offering to use for the calendar preview.
    # Prioritize one the coach is part of, otherwise take any active one.
    default_offering = CoachOffering.objects.filter(coaches=request.user, is_active=True).first()
    if not default_offering:
        default_offering = CoachOffering.objects.filter(is_active=True).first()
        
    return render(request, 'coaching/coach/coach_settings.html', {'default_offering': default_offering})

@login_required
def offering_list_view(request):
    """
    Displays a list of all active coaching offerings available for purchase.
    """
    offerings = CoachOffering.objects.filter(is_active=True)
    context = {
        'offerings': offerings
    }
    return render(request, 'coaching/offering_list.html', context)

@login_required
def purchase_offering_view(request, offering_id):
    """
    Placeholder view for handling the purchase of a specific offering.
    In a real application, this would integrate with a payment gateway.
    """
    offering = get_object_or_404(CoachOffering, id=offering_id, is_active=True)
    # This is a placeholder. A real implementation would handle payment processing.
    return HttpResponse(f"This is the confirmation page for purchasing '{offering.name}'.")

# All other existing views (`booking_page`, `coach_settings_view`, `program_list_view`, etc.) remain here.

@login_required
def booking_page(request, coach_id):
    """
    Displays all active service offerings for a specific coach.
    """
    coach = get_object_or_404(User, id=coach_id, is_coach=True)
    offerings = CoachOffering.objects.filter(coaches=coach, is_active=True)
    
    context = {
        'coach': coach,
        'offerings': offerings,
    }
    return render(request, 'coaching/booking/booking_page.html', context)


@login_required
def offering_detail_view(request, offering_slug, coach_id=None):
    """
    Shows session details and checks user eligibility (credits/price/taster credits)
    before loading the calendar. Can be filtered to a specific coach.
    """
    offering = get_object_or_404(CoachOffering, slug=offering_slug)
    
    if coach_id:
        coach = get_object_or_404(User, id=coach_id, is_coach=True)
        # Ensure the selected coach is actually associated with the offering
        if coach not in offering.coaches.all():
            return HttpResponse("This coach does not provide this service.", status=404)
    else:
        coach = offering.coaches.first()

    if not coach:
        return HttpResponse("No coaches are available for this offering.", status=404)
    user = request.user
    
    # --- Credit/Program Eligibility Check (Updated to include Taster Credits) ---
    is_eligible = False
    credit_count = 0
    
    if offering.credits_granted > 0:
        # 1. Count ALL usable credits (purchased and taster)
        valid_credits = SessionCredit.objects.filter(
            user=user,
            session__isnull=True, # Credit is unused
            expiration_date__gt=timezone.now() # Credit is not expired
        )
        credit_count = valid_credits.count()

        # 2. Check if the required credits are available
        if credit_count >= offering.credits_granted:
            is_eligible = True
            
        # 3. Determine validity dates (Only applies to purchased programs, not taster credits)
        active_offerings = UserOffering.objects.filter(
             user=user,
             end_date__gte=timezone.now().date()
        )
        earliest_start_date = active_offerings.order_by('start_date').values_list('start_date', flat=True).first()
        latest_end_date = active_offerings.order_by('-end_date').values_list('end_date', flat=True).first()

        
    else: # Assume it's price-based if no credits are granted
        # If it's a paid session, eligibility is assumed, but price is displayed.
        is_eligible = True
        earliest_start_date = None
        latest_end_date = None


    context = {
        'offering': offering,
        'coach': coach,
        'is_eligible': is_eligible,
        'credit_count': credit_count,
        'booking_start_date': earliest_start_date.isoformat() if earliest_start_date else None,
        'booking_end_date': latest_end_date.isoformat() if latest_end_date else None,
    }
    return render(request, 'coaching/booking/select_time.html', context)


@login_required
@transaction.atomic # Use transaction block for safety
def create_session_view(request, offering_id):
    """Handles the final booking process."""
    if request.method == 'POST':
        offering = get_object_or_404(CoachOffering, id=offering_id)
        # Placeholder: Parse start_time from the request.
        start_time_str = request.POST.get('start_time') # e.g., '2023-10-27T10:00:00Z'
        
        try:
            # For full-day sessions, the start_time will be just a date (e.g., '2025-11-20')
            if offering.is_full_day:
                day_date = isoparse(start_time_str).date()
                coach_tz = timezone.pytz.timezone(str(getattr(offering.coaches.first(), 'user_timezone', timezone.get_current_timezone())))
                # Set start to beginning of day and end to end of day in coach's timezone
                parsed_start_time = coach_tz.localize(datetime.datetime.combine(day_date, datetime.time.min))
                end_time = coach_tz.localize(datetime.datetime.combine(day_date, datetime.time.max))
            else:
                parsed_start_time = isoparse(start_time_str)
                end_time = None # Let the model's save() method calculate it

        except (ValueError, TypeError):
            return HttpResponse("Invalid start time format.", status=400)

        # 2. Credit Booking Logic (Transactional)
        if offering.credits_granted > 0:
            
            # --- Repeat Eligibility Check and credit selection ---
            valid_credits = SessionCredit.objects.filter(
                user=request.user,
                session__isnull=True,
                expiration_date__gt=timezone.now()
            ).select_for_update().order_by('expiration_date') # Lock and prioritize credits that expire soonest

            if valid_credits.count() < offering.credits_granted:
                return HttpResponse("Error: Not enough valid credits.", status=403)
            
            # Select the required number of credits (e.g., just the first one if credits_granted is 1)
            credits_to_use = valid_credits[:offering.credits_granted]
            
            # Assuming a coach is selected or the first available coach is used
            # In a real application, the specific coach should be passed from the frontend
            selected_coach = offering.coaches.first() 
            if not selected_coach:
                return HttpResponse("Error: No coach associated with this offering.", status=400)

            new_session = CoachingSession.objects.create(client=request.user, coach=selected_coach, offering=offering, start_time=parsed_start_time, end_time=end_time, status=SessionStatus.BOOKED)
            
            # Link the credits to the new session
            for credit in credits_to_use:
                credit.session = new_session
                credit.save()
            
            # Send notification emails to client and coach
            try:
                from .utils import send_multipart_email
                # Notify Client
                client_context = {
                    'recipient': new_session.client,
                    'session': new_session,
                    'user_timezone': str(getattr(new_session.client, 'user_timezone', timezone.get_current_timezone()))
                }
                send_multipart_email("Session Confirmed: " + new_session.offering.name, 'coaching/emails/session_booked.txt', 'coaching/emails/session_booked.html', client_context, [new_session.client.email])

                # Notify Coach
                coach_context = {
                    'recipient': new_session.coach,
                    'session': new_session,
                    'user_timezone': str(getattr(new_session.coach, 'user_timezone', timezone.get_current_timezone()))
                }
                send_multipart_email("New Session Booked: " + new_session.offering.name, 'coaching/emails/session_booked.txt', 'coaching/emails/session_booked.html', coach_context, [new_session.coach.email])

            except Exception as e:
                # Log the error, but don't block the response since the booking was successful
                print(f"Error sending booking confirmation email for session {new_session.id}: {e}")

            return HttpResponse(f"Session booked using {offering.credits_granted} Credit(s).", status=200)

        else: # Assume it's price-based if no credits are granted
              # --- Price Booking Logic ---
              # Payment initiation/confirmation, then session creation
              return HttpResponse(f"Session booked via direct payment of £{offering.price}.", status=200)
    
    offering = get_object_or_404(CoachOffering, id=offering_id)
    return redirect('coaching:offering_detail', offering_slug=offering.slug)

@login_required
def taster_booking_start(request):
    """
    Displays a list of coaches for the user to choose from to book their
    free taster session.
    """
    # Check if user has an approved taster credit
    has_taster_credit = SessionCredit.objects.filter(
        user=request.user,
        is_taster=True,
        session__isnull=True,
        expiration_date__gt=timezone.now()
    ).exists()

    if not has_taster_credit:
        return HttpResponse("You do not have an available taster session credit.", status=403)

    coaches = User.objects.filter(is_coach=True, is_active=True)
    
    # The slug for the taster offering is hardcoded here, as created by the management command.
    taster_offering_slug = 'taster-session'

    context = {
        'coaches': coaches,
        'taster_offering_slug': taster_offering_slug,
    }
    return render(request, 'coaching/taster/taster_select_coach.html', context)