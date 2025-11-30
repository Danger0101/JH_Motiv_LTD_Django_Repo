from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseRedirect, HttpResponse

# Assumed imports from other apps
from coaching_core.models import Offering, Workshop
from coaching_availability.utils import calculate_bookable_slots
from coaching_client.models import ContentPage
from accounts.models import CoachProfile
# from gcal.utils import create_event

from .models import ClientOfferingEnrollment, SessionBooking
# from .forms import SessionBookingForm # Assuming a form exists

from cart.utils import get_or_create_cart, get_cart_summary_data
from team.models import TeamMember

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')

    if not all([enrollment_id, coach_id, start_time_str]):
        return HttpResponse("Missing booking information.", status=400)

    try:
        enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
        coach = get_object_or_404(CoachProfile, id=coach_id)
        
        # Convert start_time string to datetime object
        # Assuming start_time_str format is 'YYYY-MM-DD HH:MM'
        start_datetime = timezone.datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        
        # Ensure the enrollment has remaining sessions
        if enrollment.remaining_sessions <= 0:
            return HttpResponse("No sessions remaining for this enrollment.", status=400)

        # Create the session booking
        SessionBooking.objects.create(
            enrollment=enrollment,
            coach=coach,
            client=request.user,
            start_datetime=start_datetime,
            # end_datetime will be calculated in the model's save method
        )
        
        # The enrollment's remaining_sessions will be decremented by the SessionBooking's save method
        
        # HTMX response to refresh the profile content or redirect
        # For now, let's redirect to the profile page to show updated bookings
        response = HttpResponseRedirect(reverse('accounts:account_profile'))
        response['HX-Redirect'] = reverse('accounts:account_profile') # For HTMX to handle full redirect
        return response

    except ClientOfferingEnrollment.DoesNotExist:
        return HttpResponse("Enrollment not found.", status=404)
    except CoachProfile.DoesNotExist:
        return HttpResponse("Coach not found.", status=404)
    except ValueError:
        return HttpResponse("Invalid date/time format.", status=400)
    except Exception as e:
        return HttpResponse(f"An error occurred: {e}", status=500)

@login_required
@require_POST
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    booking.cancel() # This method handles session forfeiture/restoration
    
    # Return the updated bookings partial
    user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
    return render(request, 'accounts/profile_bookings.html', {'user_bookings': user_bookings})

@login_required
def reschedule_session_form(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    return render(request, 'accounts/partials/reschedule_form.html', {'booking': booking})

@login_required
@require_POST
def reschedule_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    
    # For rescheduling, we need a new start time. This example assumes it's passed via POST.
    # In a real scenario, you'd likely render a form to select a new time.
    new_start_time_str = request.POST.get('new_start_time') 
    if not new_start_time_str:
        return HttpResponse("New start time is required for rescheduling.", status=400)
    
    try:
        new_start_time = timezone.datetime.strptime(new_start_time_str, '%Y-%m-%d %H:%M')
        booking.reschedule(new_start_time) # This method handles session forfeiture/rescheduling
        
        # Return the updated bookings partial
        user_bookings = SessionBooking.objects.filter(client=request.user).order_by('start_datetime')
        return render(request, 'accounts/profile_bookings.html', {'user_bookings': user_bookings})
    except ValueError:
        return HttpResponse("Invalid new start time format.", status=400)
    except Exception as e:
        return HttpResponse(f"An error occurred during rescheduling: {e}", status=500)

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
    
    # Fetch active workshops
    workshops = Workshop.objects.filter(active_status=True)

    # 2. Define Knowledge Categories (Expanded list)
    # The categories are hardcoded as requested, to avoid adding a model.
    KNOWLEDGE_CATEGORIES = [
        ('all', 'Business Coaches'),
    ]
    
    # 3. Fetch Knowledge/Content Pages
    # For the 'Backed by Research' section, we can use the ContentPage model.
    # Limiting to 3 for the homepage display.
    knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]

    # 4. Define page summary text and cart summary
    page_summary_text = "Welcome to our coaching services!"
    cart = get_or_create_cart(request)
    summary_data = get_cart_summary_data(cart)

    context = {
        'coaches': coaches,
        'offerings': offerings,
        'workshops': workshops,
        'knowledge_pages': knowledge_pages,
        'knowledge_categories': KNOWLEDGE_CATEGORIES[1:], # Exclude 'All Coaches' for the tab bar
        'page_summary_text': page_summary_text,
        'summary': summary_data,
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

class OfferEnrollmentStartView(LoginRequiredMixin, DetailView):
    """Initiates the checkout/enrollment process for a specific offering."""
    model = Offering
    template_name = 'coaching_booking/checkout_embedded.html' # Use the embedded checkout template
    
    def get_context_data(self, **kwargs):
        """Pass the Stripe Public Key and cart summary to the template."""
        context = super().get_context_data(**kwargs)
        # This key is needed by the Stripe.js library on the frontend
        context['STRIPE_PUBLIC_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        
        # Add cart summary data for the navbar
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        
        return context

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
