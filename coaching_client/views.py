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
        form = TasterRequestForm(request.POST)
        if form.is_valid():
            taster_request = form.save(commit=False)
            taster_request.client = request.user if request.user.is_authenticated else None
            taster_request.save()
            
            # Send acknowledgement email to client
            client_context = {'request': taster_request}
            send_transactional_email(
                recipient_email=taster_request.email,
                subject="Taster Session Request Received - JH Motiv LTD",
                template_name='emails/taster_request_acknowledgment.html', # Template assumed to exist
                context=client_context
            )
            
            # Notify site admin/coach
            # Logic to notify coach/admin is typically done here
            
            return redirect(reverse('coaching_client:taster_success'))
        return render(request, 'coaching_client/taster_request_form.html', {'form': form})

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