# coaching/views.py (Refactored Main File)

from django.shortcuts import render
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.decorators import login_required

from .utils import coach_is_valid

# Import all API functions from the new modules
from .api_views.vacation import coach_vacation_blocks, coach_vacation_block_detail
from .api_views.availability import coach_recurring_availability_view, coach_specific_availability_view, coach_specific_availability_detail
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

def booking_page(request, coach_id):
    return HttpResponse(f"Booking page for coach {coach_id}.")

@login_required
def coach_settings_view(request):
    if not coach_is_valid(request.user):
        return HttpResponse("Access Denied: You do not have coach privileges.", status=403)
    return render(request, 'coaching/coach_settings.html', {})
