# accounts/views.py (Updated)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .models import MarketingPreference
from allauth.account.views import LoginView, SignupView, PasswordResetView, PasswordChangeView, PasswordSetView, LogoutView, PasswordResetDoneView, PasswordResetDoneView

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    """
    Overrides the default allauth LoginView to handle HTMX requests correctly.
    When a login is successful via an HTMX request, it prevents the "page-in-page"
    effect by sending an HX-Redirect header, which tells HTMX to perform a full
    browser redirect.
    """
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
        
        # Fetch marketing preferences
        preference, created = MarketingPreference.objects.get_or_create(user=self.request.user)
        context['marketing_preference'] = preference
        
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

class ProfileDataLoadMixin:
    """
    A reusable mixin to ensure the requesting user is authenticated
    and provides user context.
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

class EnrollmentStatusHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
    """
    Renders the enrollment status partial for the authenticated user.
    """
    template_name = "coaching_booking/_enrollment_status.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Logic Stub: Fetch the latest active ClientOfferingEnrollment
        # from coaching_booking.models import ClientOfferingEnrollment
        # context['enrollment'] = ClientOfferingEnrollment.objects.filter(client=self.request.user, is_active=True).first()
        return context

class SessionListHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
    """
    Renders the upcoming sessions partial for the authenticated user.
    """
    template_name = "coaching_booking/_session_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Logic Stub: Fetch upcoming SessionBooking records
        # from coaching_booking.models import SessionBooking
        # from django.utils import timezone
        # context['sessions'] = SessionBooking.objects.filter(client=self.request.user, start_datetime__gte=timezone.now()).order_by('start_datetime')
        return context

class OrderHistoryHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
    """
    Renders the order history partial for the authenticated user.
    """
    template_name = "payments/_order_history.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Logic Stub: Fetch generic payments.Order history
        # from payments.models import Order
        # context['orders'] = Order.objects.filter(user=self.request.user).order_by('-created_at')
        return context