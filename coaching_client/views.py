from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.utils import timezone

from .models import TasterSessionRequest

class RequestTasterView(LoginRequiredMixin, CreateView):
    """
    Allows an authenticated client to submit a request for a free taster session.
    Redirects them if a request has already been made.
    """
    model = TasterSessionRequest
    fields = []  # No fields are needed from the user in the form
    template_name = 'coaching_client/taster_request_form.html' # Assumed template
    success_url = reverse_lazy('taster-request-success') # Assumed success URL

    def dispatch(self, request, *args, **kwargs):
        """Check if the user has already requested a taster session."""
        if TasterSessionRequest.objects.filter(client=self.request.user).exists():
            messages.info(request, "You have already submitted a taster session request.")
            return redirect('home') # Redirect to home or a relevant page
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        """Set the client to the currently logged-in user."""
        form.instance.client = self.request.user
        messages.success(self.request, "Your request for a taster session has been submitted successfully!")
        return super().form_valid(form)

class ApproveTasterView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Allows a staff member to approve or deny a pending taster session request.
    """
    model = TasterSessionRequest
    fields = ['status', 'notes'] # Fields the staff can edit
    template_name = 'coaching_client/taster_approve_form.html' # Assumed template
    success_url = reverse_lazy('taster-request-list') # Assumed list view for staff

    def test_func(self):
        """Ensure the user is a staff member."""
        return self.request.user.is_staff

    def form_valid(self, form):
        """Set the approver and decision timestamp automatically."""
        instance = form.save(commit=False)
        instance.approver = self.request.user
        instance.decision_at = timezone.now()
        
        if instance.status == 'APPROVED':
            messages.success(self.request, f"Taster session for {instance.client.get_full_name()} has been approved.")
        elif instance.status == 'DENIED':
            messages.warning(self.request, f"Taster session for {instance.client.get_full_name()} has been denied.")
        
        instance.save()
        return super().form_valid(form)