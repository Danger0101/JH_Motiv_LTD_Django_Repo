from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from datetime import date, timedelta

# Assumed imports from other apps
from coaching_core.models import Offering
from coaching_availability.utils import calculate_bookable_slots
from coaching_client.models import ContentPage
from accounts.models import CoachProfile
# from gcal.utils import create_event

from .models import ClientOfferingEnrollment, SessionBooking
# from .forms import SessionBookingForm # Assuming a form exists

from team.models import TeamMember

def coach_landing_view(request):
    """Renders the coach landing page, fetching all active coaches and offerings."""
    
    # 1. Fetch Coaches and Offerings
    # Ensure CoachProfile is linked to an active user and available for new clients
    coaches = CoachProfile.objects.filter(
        user__is_active=True,
        is_available_for_new_clients=True
    ).select_related('user') # Select related is good practice for performance

    # Fetch active offerings
    offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches')
    
    # 2. Define Knowledge Categories (Expanded list)
    # The categories are hardcoded as requested, to avoid adding a model.
    KNOWLEDGE_CATEGORIES = [
        ('all', 'Business Coaches'),
    ]
    
    # 3. Fetch Knowledge/Content Pages
    # For the 'Backed by Research' section, we can use the ContentPage model.
    # Limiting to 3 for the homepage display.
    knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]

    context = {
        'coaches': coaches,
        'offerings': offerings,
        'knowledge_pages': knowledge_pages,
        'knowledge_categories': KNOWLEDGE_CATEGORIES[1:], # Exclude 'All Coaches' for the tab bar
    }
    return render(request, 'coaching_booking/coach_landing.html', context)

class OfferListView(ListView):
    """Displays all active coaching offerings available for purchase/enrollment."""
    model = Offering
    template_name = 'coaching_booking/offering_list.html'
    context_object_name = 'offerings'

    def get_queryset(self):
        """Only show offerings that are marked as active."""
        # Assuming 'active_status' is a boolean field on the Offering model
        return Offering.objects.filter(active_status=True)

class OfferEnrollmentStartView(LoginRequiredMixin, DetailView):
    """Initiates the checkout/enrollment process for a specific offering."""
    model = Offering
    template_name = 'coaching_booking/enrollment_start.html'
    context_object_name = 'offering'
    # This view would typically hand off to a payment gateway.
    # After successful payment, a ClientOfferingEnrollment would be created.

class SessionBookingView(LoginRequiredMixin, FormView):
    """Allows an enrolled client to schedule a single session from available slots."""
    template_name = 'coaching_booking/session_booking_form.html'
    # form_class = SessionBookingForm # Replace with your actual form
    success_url = reverse_lazy('coaching_booking:dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        enrollment = get_object_or_404(
            ClientOfferingEnrollment, 
            pk=self.kwargs['enrollment_pk'], 
            client=self.request.user
        )
        context['enrollment'] = enrollment
        
        # 1. Calculate available slots
        # Define the date range for which to find slots (e.g., next 60 days)
        start_date = date.today()
        end_date = start_date + timedelta(days=60)
        
        available_slots = calculate_bookable_slots(
            coach_id=enrollment.coach.id,
            offering_id=enrollment.offering.id,
            start_date=start_date,
            end_date=end_date
        )
        context['available_slots'] = available_slots
        return context

    def form_valid(self, form):
        enrollment = get_object_or_404(
            ClientOfferingEnrollment, 
            pk=self.kwargs['enrollment_pk'], 
            client=self.request.user
        )
        
        # Create the SessionBooking record
        selected_slot = form.cleaned_data['selected_datetime'] # Assumes form field name
        booking = SessionBooking.objects.create(
            enrollment=enrollment,
            coach=enrollment.coach,
            client=self.request.user,
            start_datetime=selected_slot,
            # end_datetime is calculated on save by the model's save() method
        )
        
        # Trigger GCal API sync (stubbed)
        # gcal_event_id = create_event(booking)
        # booking.gcal_event_id = gcal_event_id
        # booking.save()
        
        # Decrement remaining sessions
        if enrollment.remaining_sessions > 0:
            enrollment.remaining_sessions -= 1
            enrollment.save()
            
        return super().form_valid(form)

class ClientDashboardView(LoginRequiredMixin, TemplateView):
    """A central hub for the client to see their status and upcoming sessions."""
    template_name = 'coaching_booking/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all enrollments for the user
        context['enrollments'] = ClientOfferingEnrollment.objects.filter(client=self.request.user)
        
        # Get upcoming bookings
        context['upcoming_bookings'] = SessionBooking.objects.filter(
            client=self.request.user,
            start_datetime__gte=timezone.now()
        ).order_by('start_datetime')
        return context