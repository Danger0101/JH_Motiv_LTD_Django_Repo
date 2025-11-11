# accounts/views.py (Updated)

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import MarketingPreference
from allauth.account.views import LoginView, SignupView, PasswordResetView, PasswordChangeView, PasswordSetView, LogoutView, PasswordResetDoneView, PasswordResetDoneView
from cart.utils import get_or_create_cart, get_cart_summary_data
from coaching_booking.models import ClientOfferingEnrollment, SessionBooking
from coaching_core.models import Offering
from accounts.models import CoachProfile # Assuming CoachProfile is in accounts.models or accessible

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
        
        cart = get_or_create_cart(self.request)
        summary = get_cart_summary_data(cart)
        context['summary'] = summary
        
        # Fetch marketing preferences
        preference, created = MarketingPreference.objects.get_or_create(user=self.request.user)
        context['marketing_preference'] = preference

        # Fetch user's coaching offerings (enrollments)
        context['user_offerings'] = ClientOfferingEnrollment.objects.filter(client=self.request.user).order_by('-enrolled_on')

        # Fetch user's booked sessions
        context['user_bookings'] = SessionBooking.objects.filter(client=self.request.user).order_by('start_datetime')

        # Add flags for dashboard elements
        context['is_coach'] = self.request.user.is_coach
        context['is_staff'] = self.request.user.is_staff

        if self.request.user.is_coach:
            # Fetch upcoming sessions where the current user is the coach
            context['coach_upcoming_sessions'] = SessionBooking.objects.filter(
                coach=self.request.user.coach_profile, # Assuming a reverse relation from User to CoachProfile
                start_datetime__gte=timezone.now()
            ).order_by('start_datetime')

            # Fetch clients assigned to this coach
            # This assumes ClientOfferingEnrollment has a 'coach' field or can be linked via 'offering'
            # For simplicity, let's get unique clients from sessions booked with this coach
            context['coach_clients'] = ClientOfferingEnrollment.objects.filter(
                offering__coaches=self.request.user.coach_profile, # Assuming 'offering' has a ManyToMany with 'coaches'
            ).values_list('client__username', flat=True).distinct()

        # For now, available_credits will be the same as user_offerings for simplicity
        # In a real scenario, this might be a separate model or a filtered queryset of enrollments
        context['available_credits'] = ClientOfferingEnrollment.objects.filter(
            client=self.request.user,
            remaining_sessions__gt=0,
            is_active=True,
            expiration_date__gte=timezone.now()
        ).order_by('-enrolled_on')
        
        context['active_tab'] = 'offerings' # Set default active tab
        
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
@login_required
def profile_offerings_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(client=request.user).order_by('-enrolled_on')
    available_credits = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now().date()
    ).order_by('-enrolled_on')
    return render(request, 'accounts/profile_offerings.html', {
        'user_offerings': user_offerings,
        'available_credits': available_credits,
        'active_tab': 'offerings'
    })

@login_required
def profile_bookings_partial(request):
    user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
    return render(request, 'accounts/profile_bookings.html', {
        'user_bookings': user_bookings,
        'active_tab': 'bookings'
    })

@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now().date()
    ).order_by('-enrolled_on')
    coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True) # Filter active and available coaches
    
    selected_enrollment_id = request.GET.get('enrollment_id')
    selected_enrollment = None
    if selected_enrollment_id:
        selected_enrollment = get_object_or_404(ClientOfferingEnrollment, id=selected_enrollment_id, client=request.user)

    return render(request, 'accounts/profile_book_session.html', {
        'user_offerings': user_offerings,
        'coaches': coaches,
        'selected_enrollment': selected_enrollment,
        'active_tab': 'book_session'
    })

@login_required
def get_coaches_for_offering(request):
    enrollment_id = request.GET.get('enrollment_id')
    coaches = []
    if enrollment_id:
        try:
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            # Get coaches associated with the offering of this enrollment
            coaches = enrollment.offering.coaches.filter(user__is_active=True, is_available_for_new_clients=True)
        except ClientOfferingEnrollment.DoesNotExist:
            pass # Handle error or return empty list
    
    # Render options for the coach select dropdown
    return render(request, 'accounts/partials/coach_options.html', {'coaches': coaches})

@login_required
def get_available_slots(request):
    enrollment_id = request.GET.get('enrollment_id')
    coach_id = request.GET.get('coach_id')
    
    # Placeholder for actual logic to fetch available slots
    # This would involve querying coaching_availability models and potentially Google Calendar
    available_slots = [] 
    if enrollment_id and coach_id:
        try:
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
            coach = CoachProfile.objects.get(id=coach_id)
            
            # TODO: Implement actual logic to get available slots based on coach availability and offering session length
            # For now, return some dummy data or an empty list
            available_slots = [
                {'start_time': '2025-11-15 10:00', 'end_time': '2025-11-15 11:00'},
                {'start_time': '2025-11-15 14:00', 'end_time': '2025-11-15 15:00'},
            ]
        except (ClientOfferingEnrollment.DoesNotExist, CoachProfile.DoesNotExist):
            pass

    return render(request, 'accounts/partials/available_slots.html', {'available_slots': available_slots})

# The existing HTMX views are not needed anymore as we are replacing them with the new tab structure
# class EnrollmentStatusHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
#     """
#     Renders the enrollment status partial for the authenticated user.
#     """
#     template_name = "coaching_booking/_enrollment_status.html"

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Logic Stub: Fetch the latest active ClientOfferingEnrollment
#         # from coaching_booking.models import ClientOfferingEnrollment
#         # context['enrollment'] = ClientOfferingEnrollment.objects.filter(client=self.request.user, is_active=True).first()
#         return context

# class SessionListHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
#     """
#     Renders the upcoming sessions partial for the authenticated user.
#     """
#     template_name = "coaching_booking/_session_list.html"

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Logic Stub: Fetch upcoming SessionBooking records
#         # from coaching_booking.models import SessionBooking
#         # from django.utils import timezone
#         # context['sessions'] = SessionBooking.objects.filter(client=self.request.user, start_datetime__gte=timezone.now()).order_by('start_datetime')
#         return context

# class OrderHistoryHtmxView(LoginRequiredMixin, ProfileDataLoadMixin, TemplateView):
#     """
#     Renders the order history partial for the authenticated user.
#     """
#     template_name = "payments/_order_history.html"

#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         # Logic Stub: Fetch generic payments.Order history
#         # from payments.models import Order
#         # context['orders'] = Order.objects.filter(user=self.request.user).order_by('-created_at')
#         return context