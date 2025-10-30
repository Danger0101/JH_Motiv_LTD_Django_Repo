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
    offering = get_object_or_404(CoachOffering, id=offering_id)
    context = {
        'offering': offering,
        'coach': offering.coach
    }
    return render(request, 'coaching/select_time.html', context)

@login_required
def create_session_view(request, offering_id):
    offering = get_object_or_404(CoachOffering, id=offering_id)
    # The rest of the booking logic will be implemented here
    pass
