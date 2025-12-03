from django.views.generic import ListView, DetailView, TemplateView # Added TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta, datetime
import calendar
from django.db import transaction
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings

from core.email_utils import send_transactional_email # Import the utility
from .models import ClientOfferingEnrollment, SessionBooking, OneSessionFreeOffer
from accounts.models import CoachProfile
from coaching_availability.utils import get_coach_available_slots
from coaching_core.models import Offering, Workshop
from coaching_client.models import ContentPage
from cart.utils import get_or_create_cart, get_cart_summary_data
from coaching_client.models import ContentPage

BOOKING_WINDOW_DAYS = 90

# --- EXISTING VIEWS (Preserved) ---

from facts.models import Fact

class CoachLandingView(TemplateView):
    template_name = "coaching_booking/coach_landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Common data for the landing page
        coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
        offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches')
        workshops = Workshop.objects.filter(active_status=True)
        knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]
        facts = Fact.objects.all()
        KNOWLEDGE_CATEGORIES = [('all', 'Business Coaches')] # This seems like a placeholder, adjust as needed
        cart = get_or_create_cart(self.request)

        context.update({
            'coaches': coaches,
            'offerings': offerings,
            'workshops': workshops,
            'knowledge_pages': knowledge_pages,
            'facts': facts,
            'knowledge_categories': KNOWLEDGE_CATEGORIES[1:],
            'page_summary_text': "Welcome to our coaching services!",
            'summary': get_cart_summary_data(cart),
        })
            
        return context


class OfferListView(ListView):
    model = Offering
    template_name = 'coaching_booking/offering_list.html'
    context_object_name = 'offerings'
    def get_queryset(self):
        return Offering.objects.filter(active_status=True)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

class OfferEnrollmentStartView(LoginRequiredMixin, DetailView):
    model = Offering
    template_name = 'coaching_booking/checkout_embedded.html'
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['STRIPE_PUBLIC_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        cart = get_or_create_cart(self.request)
        context['summary'] = get_cart_summary_data(cart)
        return context

# --- UPDATED BOOKING & MANAGEMENT VIEWS ---

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    free_offer_id = request.POST.get('free_offer_id') # New: for free sessions
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')

    def htmx_error(msg):
        messages.error(request, msg)
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    if not all([coach_id, start_time_str]):
        return htmx_error("Missing booking information. Please try again.")

    if not (enrollment_id or free_offer_id):
        return htmx_error("Booking requires either an enrollment or a free offer.")

    if enrollment_id and free_offer_id:
        return htmx_error("Cannot book with both an enrollment and a free offer simultaneously.")

    try:
        with transaction.atomic():
            enrollment = None
            free_offer = None
            session_length = 0
            
            if enrollment_id:
                # LOCKING: select_for_update() prevents other requests from reading this 
                # specific enrollment until this transaction finishes.
                enrollment = get_object_or_404(
                    ClientOfferingEnrollment.objects.select_for_update(), 
                    id=enrollment_id, 
                    client=request.user
                )
                
                # Now check sessions safely
                if enrollment.remaining_sessions <= 0:
                    messages.error(request, "No sessions remaining for this enrollment.")
                    response = HttpResponse(status=400)
                    response['HX-Redirect'] = reverse('accounts:account_profile')
                    return response
                session_length = enrollment.offering.session_length_minutes
            elif free_offer_id:
                free_offer = get_object_or_404(
                    OneSessionFreeOffer.objects.select_for_update(),
                    id=free_offer_id,
                    client=request.user
                )
                if not free_offer.is_approved:
                    return htmx_error("This free offer has not yet been approved by the coach.")
                if free_offer.is_redeemed:
                    return htmx_error("This free offer has already been redeemed.")
                if free_offer.is_expired:
                    return htmx_error("This free offer has expired.")
                
                # For free offers, session length is typically fixed, e.g., 60 minutes
                # Or it could be defined on the CoachProfile or a default setting
                # For now, let's assume a default of 60 minutes for free sessions
                session_length = 60 # Default for free sessions
                # Ensure the coach selected matches the coach on the free offer
                if int(coach_id) != free_offer.coach.id:
                    return htmx_error("The selected coach does not match the approved free offer.")
            
            coach_profile = get_object_or_404(CoachProfile, id=coach_id)
            
            try:
                start_datetime_naive = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M')
                start_datetime_obj = timezone.make_aware(start_datetime_naive)
            except ValueError:
                start_datetime_naive = datetime.fromisoformat(start_time_str)
                start_datetime_obj = timezone.make_aware(start_datetime_naive)

            now = timezone.now()

            if start_datetime_obj < now:
                return htmx_error("Cannot book a session in the past.")
            
            if start_datetime_obj > now + timedelta(days=BOOKING_WINDOW_DAYS):
                return htmx_error(f"Cannot book more than {BOOKING_WINDOW_DAYS} days in advance.")

            # Availability check
            available_slots = get_coach_available_slots(
                coach_profile,
                start_datetime_obj.date(),
                start_datetime_obj.date(),
                session_length,
                offering_type='one_on_one'
            )
            
            is_available = False
            for slot in available_slots:
                slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                if slot_aware == start_datetime_obj:
                    is_available = True
                    break
            
            if not is_available:
                return htmx_error("That time slot is no longer available.")

            booking = SessionBooking.objects.create(
                enrollment=enrollment, # Will be None if free_offer is used
                coach=coach_profile,
                client=request.user,
                start_datetime=start_datetime_obj,
            )

            if free_offer:
                free_offer.session = booking
                free_offer.is_redeemed = True
                free_offer.save()

            # --- Send Confirmation Emails ---
            try:
                # 1. Send confirmation to the client
                dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
                client_context = {
                    'user': request.user,
                    'session': booking,
                    'dashboard_url': dashboard_url,
                    'is_free_session': bool(free_offer),
                }
                send_transactional_email(
                    recipient_email=request.user.email,
                    subject="Your Coaching Session is Confirmed!",
                    template_name='emails/booking_confirmation.html',
                    context=client_context
                )

                # 2. Send notification to the coach
                coach_context = {
                    'coach': coach_profile,
                    'client': request.user,
                    'session': booking,
                    'is_free_session': bool(free_offer),
                }
                send_transactional_email(
                    recipient_email=coach_profile.user.email,
                    subject=f"New Session Booked with {request.user.get_full_name()}",
                    template_name='emails/coach_notification.html',
                    context=coach_context
                )
            except Exception as e:
                # Log the email error but do not fail the booking
                print(f"CRITICAL: Booking succeeded but failed to send confirmation emails. Error: {e}")
        
        # Success response...
        messages.success(request, f"Session confirmed for {start_datetime_obj.strftime('%B %d, %Y at %I:%M %p')}. A confirmation email has been sent.")
        response = HttpResponse(status=204)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response

    except Exception as e:
        return htmx_error(f"An error occurred: {str(e)}")


@login_required
@require_POST
@transaction.atomic
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    coach = booking.coach
    client = booking.client
    
    is_refunded = booking.cancel()
    
    # Prepare email messages
    if is_refunded:
        client_msg = "Your session credit has been successfully restored to your account."
        messages.success(request, "Session canceled successfully. Your credit has been restored.")
    else:
        client_msg = "Your session was canceled. Because this was within 24 hours of the start time, the session credit was forfeited per our Terms of Service."
        messages.warning(request, "Session canceled. The credit was forfeited due to late cancellation.")

    # Send emails
    try:
        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
        
        # 1. Email to Client
        send_transactional_email(
            recipient_email=client.email,
            subject="Your Coaching Session Has Been Canceled",
            template_name='emails/cancellation_confirmation.html',
            context={
                'user': client,
                'session': booking,
                'cancellation_message': client_msg,
                'dashboard_url': dashboard_url,
            }
        )

        # 2. Email to Coach
        send_transactional_email(
            recipient_email=coach.user.email,
            subject=f"Session Canceled by {client.get_full_name()}",
            template_name='emails/coach_cancellation_notification.html',
            context={
                'coach': coach,
                'client': client,
                'session': booking,
                'dashboard_url': dashboard_url,
            }
        )
    except Exception as e:
        print(f"CRITICAL: Cancellation for booking {booking.id} succeeded but failed to send emails. Error: {e}")

    # The view returns a partial HTML to be rendered by HTMX
    return render(request, 'accounts/profile_bookings.html', {'active_tab': 'canceled'})


@login_required
def reschedule_session_form(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    return render(request, 'accounts/partials/reschedule_form.html', {'booking': booking})


@login_required
@require_POST
def reschedule_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    new_start_time_str = request.POST.get('new_start_time')

    if not new_start_time_str:
        messages.error(request, "Please select a new time.")
    else:
        try:
            new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
            new_start_time = timezone.make_aware(new_start_time)

            session_length = booking.enrollment.offering.session_length_minutes
            available_slots = get_coach_available_slots(
                booking.coach, new_start_time.date(), new_start_time.date(), session_length, 'one_on_one'
            )
            
            is_available = False
            for slot in available_slots:
                 slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                 if slot_aware == new_start_time:
                     is_available = True
                     break

            if not is_available:
                messages.error(request, "That time slot is no longer available. Please choose another.")
            else:
                original_start_time = booking.start_time
                result = booking.reschedule(new_start_time)

                if result == 'LATE':
                    messages.error(request, "Sessions cannot be rescheduled within 24 hours of the start time.")
                else:
                    messages.success(request, f"Session successfully rescheduled to {new_start_time.strftime('%B %d, %H:%M')}.")
                    
                    # --- Send Reschedule Emails ---
                    try:
                        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
                        
                        # 1. Email to Client
                        send_transactional_email(
                            recipient_email=booking.client.email,
                            subject="Your Coaching Session Has Been Rescheduled",
                            template_name='emails/reschedule_confirmation.html',
                            context={
                                'user': booking.client,
                                'session': booking,
                                'original_start_time': original_start_time,
                                'dashboard_url': dashboard_url,
                            }
                        )

                        # 2. Email to Coach
                        send_transactional_email(
                            recipient_email=booking.coach.user.email,
                            subject=f"Session Rescheduled by {booking.client.get_full_name()}",
                            template_name='emails/coach_reschedule_notification.html',
                            context={
                                'coach': booking.coach,
                                'client': booking.client,
                                'session': booking,
                                'original_start_time': original_start_time,
                                'dashboard_url': dashboard_url,
                            }
                        )
                    except Exception as e:
                        print(f"CRITICAL: Reschedule for booking {booking.id} succeeded but failed to send emails. Error: {e}")

        except ValueError:
            messages.error(request, "Invalid date format.")
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

    # Fixed: Pass 'active_tab' context
    return render(request, 'accounts/profile_bookings.html', {'active_tab': 'upcoming'})


@login_required
@require_POST
def apply_for_free_session(request):
    coach_id = request.POST.get('coach_id')
    client = request.user

    # Prevent multiple pending/approved free offers for the same client
    if OneSessionFreeOffer.objects.filter(client=client, is_redeemed=False, is_expired=False).exclude(is_approved=False, redemption_deadline__lt=timezone.now()).exists():
        messages.warning(request, "You already have a pending or active free session offer.")
        response = HttpResponse(status=200) # HTMX expects 200 for message display
        response['HX-Trigger'] = 'refreshProfile' # Custom event to refresh profile content
        return response

    try:
        coach = get_object_or_404(CoachProfile, id=coach_id)
        
        # Create the free offer, initially not approved
        free_offer = OneSessionFreeOffer.objects.create(
            client=client,
            coach=coach,
            is_approved=False # Coach needs to approve
        )

        # Send notification to the coach
        coach_context = {
            'coach': coach,
            'client': client,
            'offer': free_offer,
            'approval_url': request.build_absolute_uri(reverse('admin:coaching_booking_onesessionfreeoffer_change', args=[free_offer.pk]))
        }
        send_transactional_email(
            recipient_email=coach.user.email,
            subject=f"New Free Session Request from {client.get_full_name()}",
            template_name='emails/coach_free_session_request.html', # Need to create this template
            context=coach_context
        )
        
        messages.success(request, "Your free session request has been sent to the coach for approval.")
        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'refreshProfile'
        return response

    except CoachProfile.DoesNotExist:
        messages.error(request, "Selected coach does not exist.")
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
    
    response = HttpResponse(status=400) # Indicate an error occurred
    response['HX-Trigger'] = 'refreshProfile'
    return response


@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True,
        expiration_date__gte=timezone.now()
    ).select_related('offering')

    # Fetch approved, non-redeemed, non-expired free offers for the client
    free_offers = OneSessionFreeOffer.objects.filter(
        client=request.user,
        is_approved=True,
        is_redeemed=False,
        redemption_deadline__gte=timezone.now()
    ).select_related('coach__user')

    coaches = CoachProfile.objects.filter(
        user__is_active=True,
        is_available_for_new_clients=True
    ).select_related('user')
    
    today = timezone.now().date()

    context = {
        'user_offerings': user_offerings,
        'free_offers': free_offers, # Add free offers to context
        'coaches': coaches,
        'initial_year': today.year,
        'initial_month': today.month,
        'selected_enrollment_id': '', 
        'selected_coach_id': '',      
        'selected_free_offer_id': '', # Add for initial selection
    }
    return render(request, 'coaching_booking/profile_book_session.html', context)


@login_required
@require_POST
def coach_approve_free_session(request):
    offer_id = request.POST.get('offer_id')
    coach_user = request.user

    try:
        coach_profile = CoachProfile.objects.get(user=coach_user)
    except CoachProfile.DoesNotExist:
        messages.error(request, "You are not recognized as a coach.")
        return HttpResponse(status=403)

    try:
        free_offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)

        if free_offer.coach != coach_profile:
            messages.error(request, "You are not authorized to approve this offer.")
            return HttpResponse(status=403)

        if free_offer.is_approved:
            messages.info(request, "This offer has already been approved.")
            return HttpResponse(status=200)
            
        if free_offer.is_redeemed:
            messages.info(request, "This offer has already been redeemed.")
            return HttpResponse(status=200)

        free_offer.is_approved = True
        free_offer.save()

        # Send notification to the client
        client_context = {
            'client': free_offer.client,
            'coach': coach_profile,
            'offer': free_offer,
            'dashboard_url': request.build_absolute_uri(reverse('accounts:account_profile'))
        }
        send_transactional_email(
            recipient_email=free_offer.client.email,
            subject=f"Your Free Session with {coach_profile.user.get_full_name()} is Approved!",
            template_name='emails/client_free_session_approved.html', # Need to create this template
            context=client_context
        )
        
        messages.success(request, f"Free session offer for {free_offer.client.get_full_name()} approved.")
        response = HttpResponse(status=200)
        response['HX-Trigger'] = 'refreshProfile'
        return response

    except OneSessionFreeOffer.DoesNotExist:
        messages.error(request, "Free session offer not found.")
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")
    
    response = HttpResponse(status=400)
    response['HX-Trigger'] = 'refreshProfile'
    return response

@login_required
def get_booking_calendar(request):
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    if not coach_id or not enrollment_id:
        return HttpResponse(
            '&lt;div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center h-full flex flex-col justify-center items-center"&gt;'
            '&lt;p class="text-gray-500 font-medium"&gt;Select an Offering and a Coach to view availability.&lt;/p&gt;'
            '&lt;/div&gt;'
        )

    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    date_obj = date(year, month, 1)
    prev_date = date_obj - timedelta(days=1)
    prev_month = prev_date.month
    prev_year = prev_date.year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    cal = calendar.Calendar(firstweekday=0)
    calendar_rows = cal.monthdayscalendar(year, month)
    today = timezone.now().date()
    max_date = today + timedelta(days=BOOKING_WINDOW_DAYS)

    context = {
        'calendar_rows': calendar_rows,
        'year': year,
        'month': month,
        'current_month_name': date_obj.strftime('%B'),
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'max_date': max_date,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)


@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')

    context = {
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'selected_date': None,
        'available_slots': [],
        'error_message': None
    }

    if not all([date_str, coach_id, enrollment_id]):
        context['error_message'] = 'Please select an offering and a coach first.'
        return render(request, 'coaching_booking/partials/available_slots.html', context)

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        context['selected_date'] = selected_date
        now = timezone.now()
        max_date = now.date() + timedelta(days=BOOKING_WINDOW_DAYS)

        if selected_date < now.date():
            context['error_message'] = 'Cannot book dates in the past.'
            return render(request, 'coaching_booking/partials/available_slots.html', context)
        
        if selected_date > max_date:
            context['error_message'] = 'This date is too far in the future.'
            return render(request, 'coaching_booking/partials/available_slots.html', context)

        coach_profile = CoachProfile.objects.get(id=coach_id)
        enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
        session_length = enrollment.offering.session_length_minutes
        
        available_slots = get_coach_available_slots(
            coach_profile,
            selected_date,
            selected_date, 
            session_length,
            offering_type='one_on_one'
        )
        
        formatted_slots = []
        for slot in available_slots:
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            if slot_aware > now:
                formatted_slots.append({
                    'start_time': slot_aware,
                    'end_time': slot_aware + timedelta(minutes=session_length)
                })

        context['available_slots'] = formatted_slots

    except (ValueError, CoachProfile.DoesNotExist, ClientOfferingEnrollment.DoesNotExist):
        context['error_message'] = 'Invalid request data.'
    except Exception as e:
        context['error_message'] = f'Error fetching slots: {str(e)}'

    return render(request, 'coaching_booking/partials/available_slots.html', context)