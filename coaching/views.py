# coaching/views.py (Refactored Main File)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from .utils import coach_is_valid
from .models import CoachingProgram, UserProgram, Token

# Import all API functions from the new modules
from .api_views.vacation import coach_vacation_blocks, coach_vacation_block_detail
from .api_views.availability import coach_recurring_availability_view, coach_specific_availability_view, coach_specific_availability_detail, coach_add_availability_modal_view, coach_create_availability_from_modal_view, coach_calendar_view
from .api_views.offerings import coach_offerings_list_create, coach_offerings_detail

class CoachingOverview(TemplateView):
    template_name = 'coaching/coaching_overview.html'

# --- Placeholder/Integration Functions (Remains Here) ---

def get_coach_availability(coach_user):
    # Placeholder logic for Google Calendar integration
    return ["9:00 AM", "10:00 AM", "11:00 AM"]

def calendar_link_init(request):
    return HttpResponse("OAuth flow initiation.")

def calendar_link_callback(request):
    return HttpResponse("OAuth callback handled.")

from django.contrib.auth import get_user_model
from .models import CoachOffering

User = get_user_model()

def booking_page(request, coach_id):
    """Displays a list of a coach's offerings to start the booking process."""
    coach = get_object_or_404(User, id=coach_id, is_coach=True)
    offerings = CoachOffering.objects.filter(coach=coach, is_active=True)
    
    context = {
        'coach': coach,
        'offerings': offerings
    }
    return render(request, 'coaching/booking_page.html', context)

@login_required
def coach_settings_view(request):
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
    return render(request, 'coaching/coach_settings.html', {})

def program_list_view(request):
    """Displays a list of all active coaching programs available for purchase."""
    programs = CoachingProgram.objects.filter(is_active=True)
    return render(request, 'coaching/program_list.html', {'programs': programs})

@login_required
def purchase_program_view(request, program_id):
    """
    Handles the "purchase" of a coaching program. In this simplified version,
    it directly creates the UserProgram and associated Tokens without a payment flow.
    """
    program = get_object_or_404(CoachingProgram, id=program_id, is_active=True)
    
    # Create the UserProgram record
    user_program = UserProgram.objects.create(
        user=request.user,
        program=program,
        purchase_date=timezone.now().date()
    )
    
    # Create the tokens for the user
    for _ in range(program.tokens_granted):
        Token.objects.create(
            user=request.user,
            user_program=user_program,
            purchase_date=timezone.now()
        )
    
    # Redirect to a success page or user profile
    # Assuming a profile page exists at /accounts/profile/
    return redirect('accounts:profile') # Make sure you have a URL named 'accounts:profile'

@login_required
def offering_detail_view(request, offering_id):
    """
    Shows session details and checks user eligibility (tokens/price)
    before loading the calendar.
    """
    offering = get_object_or_404(CoachOffering, id=offering_id)
    coach = offering.coach
    user = request.user
    
    # --- Token/Program Eligibility Check ---
    is_eligible = False
    token_count = 0
    
    if offering.booking_type == 'token':
        # 1. Check for valid, active programs for this user/offering
        active_programs = UserProgram.objects.filter(
            user=user,
            end_date__gte=timezone.now().date()
        ).select_related('program')

        # 2. Count unused, unexpired tokens associated with these programs
        valid_tokens = Token.objects.filter(
            user=user,
            session__isnull=True, # Token is unused
            expiration_date__gt=timezone.now(), # Token is not expired
            user_program__in=active_programs # Token is tied to an active program
        )
        token_count = valid_tokens.count()
        
        if token_count >= offering.tokens_required:
            is_eligible = True
            
        # Determine the earliest program start date for calendar filter (Optional, but useful)
        earliest_start_date = active_programs.order_by('start_date').values_list('start_date', flat=True).first()
        latest_end_date = active_programs.order_by('-end_date').values_list('end_date', flat=True).first()
        
    elif offering.booking_type == 'price':
        # If it's a paid session, eligibility is assumed, but price is displayed.
        is_eligible = True
        earliest_start_date = None
        latest_end_date = None


    context = {
        'offering': offering,
        'coach': coach,
        'is_eligible': is_eligible,
        'token_count': token_count,
        # Pass dates to filter the calendar view load request
        'booking_start_date': earliest_start_date.isoformat() if earliest_start_date else None,
        'booking_end_date': latest_end_date.isoformat() if latest_end_date else None,
    }
    return render(request, 'coaching/select_time.html', context)


@login_required
def create_session_view(request, offering_id):
    """Handles the final booking process."""
    if request.method == 'POST':
        # 1. Fetch data
        offering = get_object_or_404(CoachOffering, id=offering_id)
        # Parse start_time and required token logic here
        
        # 2. Token Booking Logic (Transactional)
        if offering.booking_type == 'token':
            
            # --- Repeat Eligibility Check as a safety measure ---
            valid_tokens = Token.objects.filter(
                user=request.user,
                session__isnull=True,
                expiration_date__gt=timezone.now()
            ).select_for_update() # Lock tokens for transaction

            if valid_tokens.count() < offering.tokens_required:
                return HttpResponse("Error: Not enough valid tokens.", status=403)
            
            # Use one token and link it to the session (pseudo-session creation)
            token_to_use = valid_tokens.first() # Or select based on earliest expiry
            
            # *** Placeholder: Create CoachingSession object and link token here ***
            # new_session = CoachingSession.objects.create(...)
            # token_to_use.session = new_session
            # token_to_use.save()
            
            return HttpResponse(f"Session booked using Token {token_to_use.id}.", status=200)

        elif offering.booking_type == 'price':
             # --- Price Booking Logic ---
             # Payment initiation/confirmation, then session creation
             return HttpResponse(f"Session booked via direct payment of £{offering.price}.", status=200)

    return redirect('coaching:offering_detail', offering_id=offering_id)