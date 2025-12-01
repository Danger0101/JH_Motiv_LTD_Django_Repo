from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from datetime import date, timedelta, datetime # Import datetime and date
import calendar
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseRedirect, HttpResponse

# Assumed imports from other apps
from coaching_core.models import Offering, Workshop
from coaching_availability.utils import get_coach_available_slots # Use the new utility function
from coaching_client.models import ContentPage
from accounts.models import CoachProfile
# from gcal.utils import create_event

from .models import ClientOfferingEnrollment, SessionBooking

from cart.utils import get_or_create_cart, get_cart_summary_data
from team.models import TeamMember

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')

    if not all([enrollment_id, coach_id, start_time_str]):
        messages.error(request, "Missing booking information.")
        response = HttpResponse(status=400)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    try:
        enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        
        # Convert start_time string to datetime object
        start_datetime_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        
        # Ensure the enrollment has remaining sessions
        if enrollment.remaining_sessions <= 0:
            messages.error(request, "No sessions remaining for this enrollment.")
            response = HttpResponse(status=400)
            response['HX-Redirect'] = reverse('accounts:account_profile')
            return response

        with transaction.atomic():
            # --- Re-verify availability to prevent race conditions and enforce double-booking rules ---
            session_length_minutes = enrollment.offering.session_length_minutes
            
            # Check only for the day of the requested slot to optimize
            requested_date = start_datetime_obj.date()
            
            # Call the new utility function to get truly available slots for this specific request
            # Assuming sessions booked via ClientOfferingEnrollment are 'one_on_one'
            truly_available_slots = get_coach_available_slots(
                coach_profile,
                requested_date,
                requested_date, # Check only for this specific day
                session_length_minutes,
                offering_type='one_on_one'
            )

            if start_datetime_obj not in truly_available_slots:
                messages.error(request, "The selected slot is no longer available or conflicts with another booking.")
                response = HttpResponse(status=409) # 409 Conflict
                response['HX-Redirect'] = reverse('accounts:account_profile')
                return response

            # Create the session booking
            SessionBooking.objects.create(
                enrollment=enrollment,
                coach=coach_profile,
                client=request.user,
                start_datetime=start_datetime_obj,
                # end_datetime will be calculated in the model's save method
            )
        
        messages.success(request, f"Session confirmed for {start_datetime_obj.strftime('%B %d, %Y at %I:%M %p')}.")
        
        # HTMX response to refresh the profile content or redirect
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('accounts:account_profile') # For HTMX to handle full redirect
        return response

    except ClientOfferingEnrollment.DoesNotExist:
        messages.error(request, "Enrollment not found.")
        response = HttpResponse(status=404)
    except CoachProfile.DoesNotExist:
        messages.error(request, "Coach not found.")
        response = HttpResponse(status=404)
    except ValueError:
        messages.error(request, "Invalid date/time format.")
        response = HttpResponse(status=400)
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
        response = HttpResponse(status=500)
    
    response['HX-Redirect'] = reverse('accounts:account_profile')
    return response

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
        new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%d %H:%M')
        
        # --- Re-verify availability for rescheduling to prevent race conditions and enforce double-booking rules ---
        session_length_minutes = booking.enrollment.offering.session_length_minutes
        requested_date = new_start_time.date()
        
        # Get all available slots for the new date, excluding the *original* booking's slot
        # This is tricky: we want to allow rescheduling into the original slot if it's the same,
        # but the current `get_coach_available_slots` would filter it out.
        # A simpler approach for now: check if the new slot is available generally.
        # The `get_coach_available_slots` implicitly accounts for *other* bookings.
        # If the user wants to reschedule *into their own original slot*, that would already
        # be marked as booked and unavailable by `get_coach_available_slots`.
        # For a true reschedule, we'd ideally temporarily "unbook" the old slot for the check.
        # For simplicity, for rescheduling, we treat it as if they are booking a *new* slot,
        # and their old slot will become free when the old booking is updated/canceled.
        
        truly_available_slots = get_coach_available_slots(
            booking.coach, # CoachProfile object
            requested_date,
            requested_date, # Check only for this specific day
            session_length_minutes,
            offering_type='one_on_one'
        )

        if new_start_time not in truly_available_slots:
            return HttpResponse("The selected new slot is no longer available or conflicts with another booking.", status=409)
            
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
    return context

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

# ... existing imports and views ...

@login_required
def profile_book_session_partial(request):
    """
    Renders the initial 'Book Session' tab content.
    """
    # Fetch active enrollments for the user
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).select_related('offering')

    # Fetch all available coaches
    coaches = CoachProfile.objects.filter(
        user__is_active=True,
        is_available_for_new_clients=True
    ).select_related('user')
    
    today = timezone.now().date()

    context = {
        'user_offerings': user_offerings,
        'coaches': coaches,
        'initial_year': today.year,
        'initial_month': today.month,
        # Update these lines:
        'selected_enrollment': None,
        'selected_coach': None,
        'selected_enrollment_id': '', # Add this safe primitive
        'selected_coach_id': '',      # Add this safe primitive
    }
    return render(request, 'coaching_booking/profile_book_session.html', context)

@login_required
def get_booking_calendar(request):
    """
    Returns the HTML for the calendar widget (HTMX).
    """
    # Get parameters
    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    # Calculate Month Navigation
    date_obj = date(year, month, 1)
    
    # Previous Month
    prev_date = date_obj - timedelta(days=1)
    prev_month = prev_date.month
    prev_year = prev_date.year
    
    # Next Month
    # careful with December
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    # Generate Calendar Grid
    cal = calendar.Calendar(firstweekday=0) # 0 = Monday
    calendar_rows = cal.monthdayscalendar(year, month)
    
    current_month_name = date_obj.strftime('%B')

    context = {
        'calendar_rows': calendar_rows,
        'year': year,
        'month': month,
        'current_month_name': current_month_name,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': timezone.now().date(),
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)

@login_required
def get_daily_slots(request):
    """
    Returns the available time slots for a specific date (HTMX).
    """
    date_str = request.GET.get('date')
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    if not all([date_str, coach_id, enrollment_id]):
        return render(request, 'coaching_booking/partials/available_slots.html', {
            'error_message': 'Please select an offering and a coach first.'
        })

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        coach_profile = CoachProfile.objects.get(id=coach_id)
        enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
        
        # Get session length from the offering
        session_length = enrollment.offering.session_length_minutes
        
        # Calculate slots
        available_slots = get_coach_available_slots(
            coach_profile,
            selected_date,
            selected_date, # Check just this one day
            session_length,
            offering_type='one_on_one'
        )
        
        # available_slots is a list of datetime objects.
        # We need to construct objects that templates can easily use if needed, 
        # but the list of datetimes is usually sufficient for the template loop.
        formatted_slots = []
        for slot in available_slots:
            formatted_slots.append({
                'start_time': slot,
                'end_time': slot + timedelta(minutes=session_length)
            })

        context = {
            'available_slots': formatted_slots,
            'selected_date': selected_date,
        }
    except (ValueError, CoachProfile.DoesNotExist, ClientOfferingEnrollment.DoesNotExist):
        context = {'error_message': 'Invalid request data.'}
    except Exception as e:
        context = {'error_message': f'Error fetching slots: {str(e)}'}

    return render(request, 'coaching_booking/partials/available_slots.html', context)