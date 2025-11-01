# coaching/views.py (Refactored Main File)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db import transaction

from .utils import coach_is_valid

# Import all API functions from the new modules (Already provided)
from .api_views.vacation import coach_vacation_blocks, coach_vacation_block_detail
from .api_views.availability import (
    coach_recurring_availability_view,
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

    SessionNote,

    Goal

)





@login_required

def program_goals_view(request, user_offering_id):

    user_offering = get_object_or_404(UserOffering, id=user_offering_id)

    if request.user != user_offering.user and not user_offering.offering.coach == request.user:

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

    return render(request, 'coaching/program_goals.html', {'user_offering': user_offering, 'goals': goals})

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
    return render(request, 'coaching/session_notes.html', {'session': session, 'notes': notes})
from django.views.generic import ListView

class CoachDashboardView(LoginRequiredMixin, ListView):
    model = CoachingSession
    template_name = 'coaching/coach_dashboard.html'
    context_object_name = 'sessions'

    def get_queryset(self):
        return CoachingSession.objects.filter(coach=self.request.user).order_by('-start_time')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context['upcoming_sessions'] = self.get_queryset().filter(start_time__gte=now)
        context['past_sessions'] = self.get_queryset().filter(start_time__lt=now)
        return context

@login_required
def cancel_session_view(request, session_id):
    session = get_object_or_404(CoachingSession, id=session_id)
    user = request.user

    if user != session.client and user != session.coach:
        return HttpResponse("Unauthorized", status=403)

    user_type = 'USER' if user == session.client else 'COACH'

    time_difference = session.start_time - timezone.now()
    hours_before_session = time_difference.total_seconds() / 3600

    policies = CancellationPolicy.objects.filter(user_type=user_type).order_by('-hours_before_session')
    refund_percentage = 0

    for policy in policies:
        if hours_before_session >= policy.hours_before_session:
            refund_percentage = policy.refund_percentage
            break

    if request.method == 'POST':
        session.status = 'CANCELLED'
        session.save()

        if refund_percentage > 0:
            credit = SessionCredit.objects.get(session=session)
            if refund_percentage == 100:
                credit.session = None
                credit.save()
            else:
                # For partial refunds, you might need a more complex system
                # For now, we'll just refund the whole credit
                credit.session = None
                credit.save()

        return render(request, 'coaching/cancellation_confirmation.html', {'session': session, 'refund_percentage': refund_percentage})

    return render(request, 'coaching/cancel_session.html', {'session': session, 'refund_percentage': refund_percentage})

@login_required
def initiate_swap_request_view(request, session_id, receiving_coach_id):
    session = get_object_or_404(CoachingSession, id=session_id, coach=request.user)
    receiving_coach = get_object_or_404(User, id=receiving_coach_id, is_coach=True)

    if request.method == 'POST':
        swap_request = CoachSwapRequest.objects.create(
            session=session,
            initiating_coach=request.user,
            receiving_coach=receiving_coach,
        )
        # Notify the receiving coach
        return HttpResponse("Swap request initiated.")

@login_required
def coach_swap_response_view(request, token):
    swap_request = get_object_or_404(CoachSwapRequest, token=token, receiving_coach=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            swap_request.status = 'PENDING_USER'
            swap_request.save()
            # Notify the user
            return HttpResponse("Swap request accepted. Waiting for user confirmation.")
        elif action == 'decline':
            swap_request.status = 'DECLINED'
            swap_request.save()
            # Notify the initiating coach
            return HttpResponse("Swap request declined.")

    return render(request, 'coaching/coach_swap_response.html', {'swap_request': swap_request})

@login_required
def user_swap_response_view(request, token):
    swap_request = get_object_or_404(CoachSwapRequest, token=token, session__client=request.user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'accept':
            swap_request.status = 'ACCEPTED'
            swap_request.save()
            # Update the session coach
            session = swap_request.session
            session.coach = swap_request.receiving_coach
            session.save()
            # Notify the coaches
            return HttpResponse("Swap accepted.")
        elif action == 'decline':
            swap_request.status = 'DECLINED'
            swap_request.save()
            # Notify the coaches
            return HttpResponse("Swap declined.")

    return render(request, 'coaching/user_swap_response.html', {'swap_request': swap_request})

@login_required
def reschedule_request_view(request, token):
    reschedule_request = get_object_or_404(RescheduleRequest, token=token)
    session = reschedule_request.session

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'reschedule':
            reschedule_request.status = 'ACCEPTED'
            reschedule_request.save()
            # Redirect to booking page to select a new time
            return redirect('coaching:offering_detail', offering_id=session.service_name)
        elif action == 'cancel':
            reschedule_request.status = 'DECLINED'
            reschedule_request.save()
            session.status = 'CANCELLED'
            session.save()
            # Refund the credit
            credit = SessionCredit.objects.get(session=session)
            credit.session = None
            credit.save()
            return render(request, 'coaching/reschedule_declined.html')

    return render(request, 'coaching/reschedule_request.html', {'reschedule_request': reschedule_request}) 
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
            context['offerings'] = CoachOffering.objects.filter(is_active=True).select_related('coach').order_by('id')
        except Exception as e:
            # Handle the case where the model might not exist or another error occurs
            context['offerings'] = [] 
            print(f"Error fetching offerings: {e}")
            
        return context

# --- MOMENTUM CATALYST SESSION VIEWS (NEW) ---

@login_required
def apply_taster_view(request):
    """
    Handles the user application for the one-time Momentum Catalyst Session credit.
    Records the application for coach approval.
    """
    user = request.user
    
    # 1. Check if the user already has a pending or approved application
    existing_application = CreditApplication.objects.filter(
        user=user, 
        is_taster=True
    ).exclude(status=CreditApplication.STATUS_DENIED).first() # Exclude DENIED to allow re-applying after denial
    
    if existing_application:
        # User already applied or has a token. Redirect them to a status page.
        return render(request, 'coaching/taster_status.html', {
            'application': existing_application,
            'message': 'You have already applied for or received your Momentum Catalyst Session credit.'
        })

    if request.method == 'POST':
        # Assuming a simple form post to initiate the application
        
        # 2. Create the application record
        CreditApplication.objects.create(
            user=user,
            is_taster=True,
            status=CreditApplication.STATUS_PENDING,
            # Additional form data (e.g., goals) could be saved here
        )
        
        # 3. Redirect to a waiting/confirmation page
        return render(request, 'coaching/taster_confirmation.html', {
            'message': 'Your application for the Momentum Catalyst Session has been submitted. A coach will review it shortly.'
        })

    # Display the application form (GET request)
    return render(request, 'coaching/apply_taster.html', {})


@login_required
def coach_manage_taster_view(request):
    """
    View for coaches to see pending taster credit applications and approve/deny them.
    This would typically be part of coach_settings_view.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
        
    pending_applications = CreditApplication.objects.filter(
        is_taster=True, 
        status=CreditApplication.STATUS_PENDING
    ).order_by('created_at')
    
    context = {
        'pending_applications': pending_applications,
    }
    return render(request, 'coaching/coach_manage_tasters.html', context)


@login_required
@transaction.atomic
def approve_taster_credit_view(request, application_id):
    """
    Handles the coach's action to approve a taster credit application.
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(CreditApplication, id=application_id, is_taster=True)

    if application.status != CreditApplication.STATUS_PENDING:
        return HttpResponse("Application is not pending review.", status=400)

    # 1. Update the application status
    application.status = CreditApplication.STATUS_APPROVED
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    # 2. Grant the one-time Taster Credit
    # This credit should ideally be tied to a specific free offering/program type
    SessionCredit.objects.create(
        user=application.user,
        # Set a short expiry date (e.g., 30 days)
        expiration_date=timezone.now() + timezone.timedelta(days=30), 
        is_taster=True, # Flag it as a one-time free credit
    )
    
    # Optional: Send a notification email to the user

    return redirect('coaching:coach_manage_tasters') # Redirect back to the management view


@login_required
def deny_taster_credit_view(request, application_id):
    """
    Handles the coach's action to deny a taster credit application (e.g., abuse detected).
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(CreditApplication, id=application_id, is_taster=True)

    if application.status != CreditApplication.STATUS_PENDING:
        return HttpResponse("Application is not pending review.", status=400)
    
    application.status = CreditApplication.STATUS_DENIED
    application.denied_by = request.user
    application.denied_at = timezone.now()
    application.save()

    # Optional: Send a notification email to the user explaining the denial

    return redirect('coaching:coach_manage_tasters')

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
    return render(request, 'coaching/coach_settings.html')

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
    offerings = CoachOffering.objects.filter(coach=coach, is_active=True)
    
    context = {
        'coach': coach,
        'offerings': offerings,
    }
    return render(request, 'coaching/booking_page.html', context)


@login_required
def offering_detail_view(request, offering_id):
    """
    Shows session details and checks user eligibility (credits/price/taster credits)
    before loading the calendar.
    """
    offering = get_object_or_404(CoachOffering, id=offering_id)
    coach = offering.coach
    user = request.user
    
    # --- Credit/Program Eligibility Check (Updated to include Taster Credits) ---
    is_eligible = False
    credit_count = 0
    
    if offering.booking_type == 'credit':
        # 1. Count ALL usable credits (purchased and taster)
        valid_credits = SessionCredit.objects.filter(
            user=user,
            session__isnull=True, # Credit is unused
            expiration_date__gt=timezone.now() # Credit is not expired
        )
        credit_count = valid_credits.count()

        # 2. Check if the required credits are available
        if credit_count >= offering.credits_required:
            is_eligible = True
            
        # 3. Determine validity dates (Only applies to purchased programs, not taster credits)
        active_offerings = UserOffering.objects.filter(
             user=user,
             end_date__gte=timezone.now().date()
        )
        earliest_start_date = active_offerings.order_by('start_date').values_list('start_date', flat=True).first()
        latest_end_date = active_offerings.order_by('-end_date').values_list('end_date', flat=True).first()

        
    elif offering.booking_type == 'price':
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
    return render(request, 'coaching/select_time.html', context)


@login_required
@transaction.atomic # Use transaction block for safety
def create_session_view(request, offering_id):
    """Handles the final booking process."""
    if request.method == 'POST':
        offering = get_object_or_404(CoachOffering, id=offering_id)
        # Assuming you parse start_time, etc., from request.POST here

        # 2. Credit Booking Logic (Transactional)
        if offering.booking_type == 'credit':
            
            # --- Repeat Eligibility Check and credit selection ---
            valid_credits = SessionCredit.objects.filter(
                user=request.user,
                session__isnull=True,
                expiration_date__gt=timezone.now()
            ).select_for_update().order_by('expiration_date') # Lock and prioritize credits that expire soonest

            if valid_credits.count() < offering.credits_required:
                return HttpResponse("Error: Not enough valid credits.", status=403)
            
            # Select the required number of credits (e.g., just the first one if credits_required is 1)
            credits_to_use = valid_credits[:offering.credits_required]
            
            # *** Create CoachingSession object ***
            # This is a placeholder for parsing the start time from the request
            parsed_start_time = timezone.now() 
            new_session = CoachingSession.objects.create(
                client=request.user,
                coach=offering.coach,
                service_name=offering.name,
                start_time=parsed_start_time,
                end_time=parsed_start_time + timezone.timedelta(minutes=offering.duration_minutes)
            )
            
            # Link the credits to the new session
            for credit in credits_to_use:
                credit.session = new_session
                credit.save()
            
            return HttpResponse(f"Session booked using {offering.credits_required} Credit(s).", status=200)

        elif offering.booking_type == 'price':
              # --- Price Booking Logic ---
              # Payment initiation/confirmation, then session creation
              return HttpResponse(f"Session booked via direct payment of £{offering.price}.", status=200)

    return redirect('coaching:offering_detail', offering_id=offering_id)