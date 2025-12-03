# coaching_client/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.generic import View, TemplateView
from django.contrib.auth.mixins import UserPassesTestMixin
from .forms import TasterRequestForm
from .models import TasterSessionRequest
from core.email_utils import send_transactional_email
import logging

logger = logging.getLogger(__name__)

# --- Public Facing View ---
class TasterRequestView(View):
    """Handles the public submission of a Taster Session Request."""
    def get(self, request, *args, **kwargs):
        form = TasterRequestForm()
        return render(request, 'coaching_client/taster_request_form.html', {'form': form})

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            # Should be blocked by frontend button, but this is the backend guardrail
            messages.error(request, "You must be logged in to submit a taster session request.")
            return redirect(reverse('account_login')) # Redirect to login page
            
        # Check for existing request (One-Application Limit)
        if TasterSessionRequest.has_active_request(request.user):
            messages.warning(request, "You already have a pending or approved taster session request. We will contact you soon!")
            return redirect(reverse('accounts:account_profile')) 
            
        # Initialize form with POST data and the request object
        form = TasterRequestForm(request.POST) # Removed request=request as it's not needed by the simplified form
        if form.is_valid():
            taster_request = form.save(commit=False)
            taster_request.client = request.user
            # Auto-populate data from the authenticated user's account
            taster_request.full_name = request.user.get_full_name()
            taster_request.email = request.user.email
            # Phone number is only passed if the field was available in the form/template
            
            taster_request.save()
            
            # Send acknowledgement email to client (using core.email_utils)
            # send_transactional_email(...) 
            
            messages.success(request, "Your taster session request has been submitted successfully and is under review.")
            return redirect(reverse('coaching_client:taster_success'))
            
        # If form validation fails, redirect back to the coach page with an error message
        messages.error(request, "There was an error in your submission. Please check the details and try again.")
        return redirect(reverse('coaching_booking:coach_landing'))

class TasterRequestSuccessView(TemplateView):
    """Displays a success message after a taster request is submitted."""
    template_name = 'coaching_client/taster_request_success.html'

# --- Staff/Coach Dashboard View ---
class TasterRequestManagerView(UserPassesTestMixin, View):
    """
    Displays pending taster session requests for approval/denial.
    Accessible only by staff/coaches.
    """
    def test_func(self):
        # Only allow staff or active coaches access
        return self.request.user.is_staff or self.request.user.is_coach

    def get(self, request, *args, **kwargs):
        # Fetch requests that need review
        pending_requests = TasterSessionRequest.objects.filter(status='PENDING').order_by('requested_at')
        
        return render(request, 
                      'accounts/partials/_taster_requests_list.html', 
                      {'taster_requests': pending_requests})

# --- Staff/Coach Action View ---
class TasterRequestActionView(UserPassesTestMixin, View):
    """Handles the acceptance or denial of a Taster Session Request."""
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_coach

    def post(self, request, pk):
        taster_request = get_object_or_404(TasterSessionRequest, pk=pk)
        action = request.POST.get('action')
        
        profile_url = request.build_absolute_uri(reverse('accounts:account_profile'))
        offer_list_url = request.build_absolute_uri(reverse('coaching_booking:offer-list'))

        if action == 'accept':
            taster_request.status = 'APPROVED'
            taster_request.save()
            
            # Send approval email to client (telling them to book a session)
            send_transactional_email(
                recipient_email=taster_request.email,
                subject="Your Taster Session Request Has Been Approved!",
                template_name='emails/taster_request_approved.html',
                context={'request': taster_request, 'profile_url': profile_url}
            )
            
        elif action == 'deny':
            taster_request.status = 'DENIED'
            taster_request.save()
            
            # Send denial email to client
            send_transactional_email(
                recipient_email=taster_request.email,
                subject="Update on Your Taster Session Request",
                template_name='emails/taster_request_denied.html',
                context={'request': taster_request, 'offer_list_url': offer_list_url}
            )

        pending_requests = TasterSessionRequest.objects.filter(status='PENDING').order_by('requested_at')
        
        return render(request, 
                      'accounts/partials/_taster_requests_list.html', 
                      {'taster_requests': pending_requests})