# coaching/views.py (Refactored Main File)

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction # Needed for safe token creation/usage

from .utils import coach_is_valid

# Import all API functions from the new modules (Already provided)
from .api_views.vacation import coach_vacation_blocks, coach_vacation_block_detail
from .api_views.availability import coach_recurring_availability_view, coach_specific_availability_view, coach_specific_availability_detail, coach_add_availability_modal_view, coach_create_availability_from_modal_view, coach_calendar_view
from .api_views.offerings import coach_offerings_list_create, coach_offerings_detail

# Model Imports (Added missing models: TokenApplication)
from django.contrib.auth import get_user_model
from .models import CoachingProgram, UserProgram, Token, CoachOffering, TokenApplication 
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
    Handles the user application for the one-time Momentum Catalyst Session token.
    Records the application for coach approval.
    """
    user = request.user
    
    # 1. Check if the user already has a pending or approved application
    existing_application = TokenApplication.objects.filter(
        user=user, 
        is_taster=True
    ).exclude(status=TokenApplication.STATUS_DENIED).first() # Exclude DENIED to allow re-applying after denial
    
    if existing_application:
        # User already applied or has a token. Redirect them to a status page.
        return render(request, 'coaching/taster_status.html', {
            'application': existing_application,
            'message': 'You have already applied for or received your Momentum Catalyst Session token.'
        })

    if request.method == 'POST':
        # Assuming a simple form post to initiate the application
        
        # 2. Create the application record
        TokenApplication.objects.create(
            user=user,
            is_taster=True,
            status=TokenApplication.STATUS_PENDING,
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
    View for coaches to see pending taster token applications and approve/deny them.
    This would typically be part of coach_settings_view.
    """
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
        
    pending_applications = TokenApplication.objects.filter(
        is_taster=True, 
        status=TokenApplication.STATUS_PENDING
    ).order_by('created_at')
    
    context = {
        'pending_applications': pending_applications,
    }
    return render(request, 'coaching/coach_manage_tasters.html', context)


@login_required
@transaction.atomic
def approve_taster_token_view(request, application_id):
    """
    Handles the coach's action to approve a taster token application.
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(TokenApplication, id=application_id, is_taster=True)

    if application.status != TokenApplication.STATUS_PENDING:
        return HttpResponse("Application is not pending review.", status=400)

    # 1. Update the application status
    application.status = TokenApplication.STATUS_APPROVED
    application.approved_by = request.user
    application.approved_at = timezone.now()
    application.save()

    # 2. Grant the one-time Taster Token
    # This token should ideally be tied to a specific free offering/program type
    Token.objects.create(
        user=application.user,
        # Set a short expiry date (e.g., 30 days)
        expiration_date=timezone.now() + timezone.timedelta(days=30), 
        is_taster=True, # Flag it as a one-time free token
    )
    
    # Optional: Send a notification email to the user

    return redirect('coaching:coach_manage_tasters') # Redirect back to the management view


@login_required
def deny_taster_token_view(request, application_id):
    """
    Handles the coach's action to deny a taster token application (e.g., abuse detected).
    """
    if not coach_is_valid(request.user) or request.method != 'POST':
        return HttpResponse("Unauthorized or Invalid Request.", status=403)

    application = get_object_or_404(TokenApplication, id=application_id, is_taster=True)

    if application.status != TokenApplication.STATUS_PENDING:
        return HttpResponse("Application is not pending review.", status=400)
    
    application.status = TokenApplication.STATUS_DENIED
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
def program_list_view(request):
    """
    Displays a list of all active coaching programs available for purchase.
    """
    programs = CoachingProgram.objects.filter(is_active=True)
    context = {
        'programs': programs
    }
    return render(request, 'coaching/program_list.html', context)

@login_required
def purchase_program_view(request, program_id):
    """
    Placeholder view for handling the purchase of a specific program.
    In a real application, this would integrate with a payment gateway.
    """
    program = get_object_or_404(CoachingProgram, id=program_id, is_active=True)
    # This is a placeholder. A real implementation would handle payment processing.
    return HttpResponse(f"This is the confirmation page for purchasing '{program.name}'.")

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
    Shows session details and checks user eligibility (tokens/price/taster tokens)
    before loading the calendar.
    """
    offering = get_object_or_404(CoachOffering, id=offering_id)
    coach = offering.coach
    user = request.user
    
    # --- Token/Program Eligibility Check (Updated to include Taster Tokens) ---
    is_eligible = False
    token_count = 0
    
    if offering.booking_type == 'token':
        # 1. Count ALL usable tokens (purchased and taster)
        valid_tokens = Token.objects.filter(
            user=user,
            session__isnull=True, # Token is unused
            expiration_date__gt=timezone.now() # Token is not expired
        )
        token_count = valid_tokens.count()

        # 2. Check if the required tokens are available
        if token_count >= offering.tokens_required:
            is_eligible = True
            
        # 3. Determine validity dates (Only applies to purchased programs, not taster tokens)
        active_programs = UserProgram.objects.filter(
             user=user,
             end_date__gte=timezone.now().date()
        )
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

        # 2. Token Booking Logic (Transactional)
        if offering.booking_type == 'token':
            
            # --- Repeat Eligibility Check and token selection ---
            valid_tokens = Token.objects.filter(
                user=request.user,
                session__isnull=True,
                expiration_date__gt=timezone.now()
            ).select_for_update().order_by('expiration_date') # Lock and prioritize tokens that expire soonest

            if valid_tokens.count() < offering.tokens_required:
                return HttpResponse("Error: Not enough valid tokens.", status=403)
            
            # Select the required number of tokens (e.g., just the first one if tokens_required is 1)
            tokens_to_use = valid_tokens[:offering.tokens_required]
            
            # *** Placeholder: Create CoachingSession object ***
            # new_session = CoachingSession.objects.create(
            #     user=request.user,
            #     coach=offering.coach,
            #     offering=offering,
            #     start_time=parsed_start_time,
            #     # ... other session details
            # )
            
            # Link the tokens to the new session
            # for token in tokens_to_use:
            #     token.session = new_session
            #     token.save()
            
            return HttpResponse(f"Session booked using {offering.tokens_required} Token(s).", status=200)

        elif offering.booking_type == 'price':
              # --- Price Booking Logic ---
              # Payment initiation/confirmation, then session creation
              return HttpResponse(f"Session booked via direct payment of £{offering.price}.", status=200)

    return redirect('coaching:offering_detail', offering_id=offering_id)