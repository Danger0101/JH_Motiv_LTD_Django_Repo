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
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        
        # Convert start_time string to datetime object
        start_datetime_obj = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
        
        # Ensure the enrollment has remaining sessions
        if enrollment.remaining_sessions <= 0:
            return HttpResponse("No sessions remaining for this enrollment.", status=400)

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
            return HttpResponse("The selected slot is no longer available or conflicts with another booking.", status=409) # 409 Conflict

        # Create the session booking
        SessionBooking.objects.create(
            enrollment=enrollment,
            coach=coach_profile,
            client=request.user,
            start_datetime=start_datetime_obj,
            # end_datetime will be calculated in the model's save method
        )
        
        # The enrollment's remaining_sessions will be decremented by the SessionBooking's save method
        
        # HTMX response to refresh the profile content or redirect
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
        
        # NOTE: This still uses the old calculate_bookable_slots.
        # This should be updated to use the new get_coach_available_slots.
        available_slots = get_coach_available_slots(
            coach_profile=enrollment.coach, # Pass coach_profile object
            start_date=start_date,
            end_date=end_date,
            session_length_minutes=enrollment.offering.session_length_minutes,
            offering_type='one_on_one'
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
        
        # Decrement remaining sessions (This is now handled in SessionBooking's save method)
        # if enrollment.remaining_sessions > 0:
        #     enrollment.remaining_sessions -= 1
        #     enrollment.save()
            
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
@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).order_by('-enrolled_on')
    coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True) # Filter active and available coaches
    
    selected_enrollment_id = request.GET.get('enrollment_id')
    selected_enrollment = None
    if selected_enrollment_id:
        selected_enrollment = get_object_or_404(ClientOfferingEnrollment, id=selected_enrollment_id, client=request.user)

    selected_coach_id = request.GET.get('coach_id')
    selected_coach = None
    if selected_coach_id:
        selected_coach = get_object_or_404(CoachProfile, id=selected_coach_id)

    # Initialize year and month for the calendar
    today = date.today()
    initial_year = today.year
    initial_month = today.month

    return render(request, 'coaching_booking/profile_book_session.html', {
        'user_offerings': user_offerings,
        'coaches': coaches,
        'selected_enrollment': selected_enrollment,
        'selected_coach': selected_coach,
        'active_tab': 'book_session',
        'initial_year': initial_year,
        'initial_month': initial_month,
    })

@login_required
def get_booking_calendar(request):
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    cal = calendar.Calendar(firstweekday=0) # Monday is 0
    # The `monthdayscalendar` method returns a list of lists of integers
    # where each integer is a day of the month or 0 for days outside the month.
    calendar_rows = cal.monthdayscalendar(year, month)

    today = date.today()

    # Calculate previous and next month/year for navigation
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    next_month_date = date(year, month, 1) + timedelta(days=32) # Go beyond to ensure next month

    context = {
        'year': year,
        'month': month,
        'current_month_name': date(year, month, 1).strftime('%B'), # Renamed from month_name
        'calendar_rows': calendar_rows, # Renamed from month_days
        'today': today,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'prev_month': prev_month_date.month,
        'prev_year': prev_month_date.year,
        'next_month': next_month_date.month,
        'next_year': next_month_date.year,
        'date': date, # Pass the date constructor for template logic
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)

@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    coach_id_str = request.GET.get('coach_id')
    enrollment_id_str = request.GET.get('enrollment_id')

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        selected_date = date.today() # Fallback to today if parsing fails

    daily_slots_data = []
    error_message = None
    
    # These are passed to the template context regardless of success/failure
    coach_id = coach_id_str
    enrollment_id = enrollment_id_str

    if not coach_id_str or not coach_id_str.isdigit():
        error_message = "Please select a coach to see available times."
    elif not enrollment_id_str or not enrollment_id_str.isdigit():
        error_message = "Please select an offering to see available times."
    else:
        try:
            # All IDs are present, proceed to fetch data
            coach_profile = CoachProfile.objects.get(id=int(coach_id_str))
            enrollment = ClientOfferingEnrollment.objects.get(id=int(enrollment_id_str), client=request.user)
            
            session_length_minutes = enrollment.offering.session_length_minutes

            if session_length_minutes <= 0:
                error_message = "The session length for this offering is not configured correctly."
            else:
                # Fetch available slots from the utility function
                generated_slots = get_coach_available_slots(
                    coach_profile,
                    selected_date,
                    selected_date,
                    session_length_minutes,
                    offering_type='one_on_one'  # As determined by business logic
                )

                # Format the slots for the template
                for slot_start_datetime in generated_slots:
                    daily_slots_data.append({
                        'display_time': slot_start_datetime.strftime('%I:%M %p'),
                        'start_datetime_iso': slot_start_datetime.isoformat(),
                    })
                
                # **CRUCIAL FIX**: Check for empty slots *after* the loop has finished
                if not daily_slots_data:
                    error_message = "No available slots for this day."

        except CoachProfile.DoesNotExist:
            error_message = "The selected coach could not be found."
        except ClientOfferingEnrollment.DoesNotExist:
            error_message = "The selected offering enrollment could not be found for your account."
        except Exception as e:
            # Generic error for unexpected issues, good for security to not expose details
            error_message = f"An unexpected error occurred: {e}"

    context = {
        'daily_slots': daily_slots_data,
        'error_message': error_message,
        'selected_date': selected_date, 
        'coach_id': coach_id, 
        'enrollment_id': enrollment_id,
    }
    return render(request, 'coaching_booking/partials/_day_slots.html', context)

@login_required
@require_POST
def book_session_confirm(request):
    """
    Handles the confirmation of a session booking. This view is triggered by a POST
    request, typically from an HTMX form.
    """
    enrollment_id = request.POST.get('enrollment_id')
    coach_id = request.POST.get('coach_id')
    start_datetime_iso = request.POST.get('start_datetime')

    try:
        # Validate input and fetch objects
        enrollment = get_object_or_404(ClientOfferingEnrollment, id=enrollment_id, client=request.user)
        coach = get_object_or_404(CoachProfile, id=coach_id)
        start_datetime = datetime.fromisoformat(start_datetime_iso)

        # Check for sufficient credits
        if enrollment.remaining_sessions <= 0:
            messages.error(request, "You have no remaining sessions for this offering.")
        else:
            # Use a transaction to ensure atomicity
            with transaction.atomic():
                # Create the booking
                SessionBooking.objects.create(
                    client=request.user,
                    coach=coach,
                    offering=enrollment.offering,
                    start_datetime=start_datetime,
                    status='confirmed'
                )
                
                # Decrement the session count
                enrollment.remaining_sessions -= 1
                enrollment.save()

            messages.success(request, f"Session confirmed for {start_datetime.strftime('%B %d, %Y at %I:%M %p')}.")

    except (ValueError, TypeError):
        messages.error(request, "Invalid booking time submitted.")
    except Exception as e:
        messages.error(request, f"An error occurred while booking the session: {e}")

    # For HTMX, redirect on success or failure to show messages
    response = HttpResponse(status=204)
    response['HX-Redirect'] = reverse('accounts:account_profile')
    return response