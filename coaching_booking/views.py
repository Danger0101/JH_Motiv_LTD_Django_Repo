from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta, datetime
import calendar
import logging
from django.db import transaction
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden
import stripe

from core.email_utils import send_transactional_email
from payments.models import CoachingOrder
from .models import ClientOfferingEnrollment, SessionBooking, OneSessionFreeOffer
from accounts.models import CoachProfile
from coaching_availability.utils import get_coach_available_slots
from coaching_core.models import Offering, Workshop
from coaching_client.models import ContentPage
from cart.utils import get_or_create_cart, get_cart_summary_data
from facts.models import Fact
from .services import BookingService
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
BOOKING_WINDOW_DAYS = 90
stripe.api_key = settings.STRIPE_SECRET_KEY

class CoachLandingView(TemplateView):
    template_name = "coaching_booking/coach_landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
        offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches')
        workshops = Workshop.objects.filter(active_status=True)
        knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]
        facts = Fact.objects.all()
        KNOWLEDGE_CATEGORIES = [('all', 'Business Coaches')]
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

@login_required
@require_POST
def book_session(request):
    enrollment_id = request.POST.get('enrollment_id')
    free_offer_id = request.POST.get('free_offer_id')
    coach_id = request.POST.get('coach_id')
    start_time_str = request.POST.get('start_time')
    workshop_id = request.POST.get('workshop_id') # Support for new flow

    def htmx_error(msg):
        # Return inline HTML for the #booking-errors div instead of redirecting
        response = HttpResponse(
            f'<div class="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg">{msg}</div>'
        )
        return response

    try:
        # Check for double booking (race condition or missing service check)
        if start_time_str and coach_id:
            try:
                # Normalize start_time_str to datetime
                # Frontend usually sends ISO format (e.g. 2023-10-25T14:00:00Z)
                clean_time = start_time_str.replace('Z', '+00:00')
                check_start_time = datetime.fromisoformat(clean_time)
                
                if timezone.is_naive(check_start_time):
                    check_start_time = timezone.make_aware(check_start_time)
                
                if SessionBooking.objects.filter(
                    coach_id=coach_id,
                    start_datetime=check_start_time,
                    status__in=['BOOKED', 'PENDING_PAYMENT', 'RESCHEDULED']
                ).exists():
                    return htmx_error("This time slot has already been booked. Please select another time.")
            except ValueError:
                pass # Let BookingService handle invalid formats

        booking_data = {
            'enrollment_id': enrollment_id,
            'free_offer_id': free_offer_id,
            'coach_id': coach_id,
            'workshop_id': workshop_id,
            'start_time': start_time_str,
            # Guest data could be pulled from POST if user is not authenticated
            'email': request.POST.get('email'),
            'name': request.POST.get('name'),
        }

        result = BookingService.create_booking(booking_data, user=request.user)
        
        if result['type'] == 'confirmed':
            booking = result['booking']
            # Email is now handled by signals.py -> tasks.py asynchronously
            messages.success(request, f"Session confirmed for {booking.start_datetime.strftime('%B %d, %Y at %I:%M %p')}. A confirmation email has been sent.")
            response = HttpResponse(status=204)
            response['HX-Redirect'] = reverse('accounts:account_profile')
            return response
            
        elif result['type'] == 'checkout':
            # Redirect to local payment page with timer
            response = HttpResponse(status=204)
            booking_id = result.get('booking_id')
            if booking_id:
                response['HX-Redirect'] = reverse('coaching_booking:session_payment_page', args=[booking_id])
            else:
                response['HX-Redirect'] = result['url']
            return response

    except ValidationError as e:
        return htmx_error(str(e.message))
    except Exception as e:
        logger.error(f"Booking Error: {e}", exc_info=True)
        return htmx_error(f"An error occurred: {str(e)}")

@login_required
def session_payment_page(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    
    if booking.status != 'PENDING_PAYMENT':
        messages.info(request, "This session is not pending payment.")
        return redirect('accounts:account_profile')

    # Calculate remaining time (15 minutes from creation)
    expiration_time = booking.created_at + timedelta(minutes=15)
    remaining_seconds = (expiration_time - timezone.now()).total_seconds()
    
    if remaining_seconds <= 0:
        messages.error(request, "This hold has expired.")
        return redirect('accounts:account_profile')

    # Retrieve Stripe URL
    checkout_url = None
    if booking.stripe_checkout_session_id:
        try:
            session = stripe.checkout.Session.retrieve(booking.stripe_checkout_session_id)
            checkout_url = session.url
        except Exception as e:
            logger.error(f"Stripe error: {e}")
    
    if not checkout_url:
         messages.error(request, "Could not retrieve payment information.")
         return redirect('accounts:account_profile')

    context = {
        'booking': booking,
        'checkout_url': checkout_url,
        'remaining_seconds': int(remaining_seconds)
    }
    return render(request, 'coaching_booking/session_payment.html', context)

@login_required
@require_POST
@transaction.atomic
def cancel_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    coach = booking.coach
    client = booking.client
    
    is_refunded = booking.cancel()
    
    if is_refunded and booking.enrollment:
        # Check if there is a related financial order
        try:
            order = CoachingOrder.objects.get(enrollment=booking.enrollment)
            
            # AUTOMATICALLY VOID COMMISSIONS
            if order.payout_status == 'unpaid':
                order.payout_status = 'void'
                order.save()
                logger.info(f"Commissions for Order {order.id} VOIDED due to session cancellation.")
            elif order.payout_status == 'paid':
                # CRITICAL ALERT: You already paid the coach, but the client got a refund!
                # You need to manually claw this back from future earnings.
                logger.warning(f"ALERT: Refund issued for PAID Order {order.id}. Manual clawback required.")
                
        except CoachingOrder.DoesNotExist:
            pass # No financial order linked, so nothing to void.
    
    client_msg = ""
    if is_refunded and booking.enrollment:
        client_msg = "Your session credit has been successfully restored to your account."
        messages.success(request, "Session canceled successfully. Your credit has been restored.")
    elif not is_refunded:
        client_msg = "Your session was canceled. As this was within 24 hours of the start time, the session credit was forfeited per our Terms of Service."
        messages.warning(request, "Session canceled. The credit was forfeited due to late cancellation.")

    try:
        # Format dates for email context
        original_date_str = booking.start_datetime.strftime("%A, %B %d, %Y")
        original_time_start_str = booking.start_datetime.strftime("%I:%M %p UTC")
        original_time_end_str = booking.end_datetime.strftime("%I:%M %p UTC")

        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
        send_transactional_email(
            recipient_email=client.email,
            subject="Your Coaching Session Has Been Canceled",
            template_name='emails/cancellation_confirmation.html',
            context={
                'user_id': client.pk,
                'booking_id': booking.pk,
                'cancellation_message': client_msg,
                'dashboard_url': dashboard_url,
                'original_date': original_date_str,
                'original_time_start': original_time_start_str,
                'original_time_end': original_time_end_str,
            }
        )

        send_transactional_email(
            recipient_email=coach.user.email,
            subject=f"Session Canceled by {client.get_full_name()}",
            template_name='emails/coach_cancellation_notification.html',
            context={
                'coach_id': coach.pk,
                'client_id': client.pk,
                'booking_id': booking.pk,
                'dashboard_url': dashboard_url,
                'original_date': original_date_str,
                'original_time_start': original_time_start_str,
                'original_time_end': original_time_end_str,
            }
        )
    except Exception as e:
        logger.error(f"CRITICAL: Cancellation for booking {booking.id} succeeded but failed to send emails. Error: {e}")

    return render(request, 'account/profile_bookings.html', {'active_tab': 'canceled'})

@login_required
def reschedule_session_form(request, booking_id):
    """
    Returns the HTMX partial for the reschedule form.
    """
    booking = get_object_or_404(SessionBooking, id=booking_id)
    
    # Security check: Ensure the user is the client or the coach for this booking
    is_client = booking.client == request.user
    is_coach = booking.coach.user == request.user
    
    if not (is_client or is_coach):
        return HttpResponseForbidden("You are not authorized to reschedule this session.")
        
    return render(request, 'account/partials/reschedule_form.html', {'booking': booking})

@login_required
@require_POST
def reschedule_session(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    
    def htmx_error(msg):
        return HttpResponse(
            f'<div class="p-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg">{msg}</div>'
        )

    # --- 1. Prevent Rescheduling Canceled Sessions ---
    if booking.status == 'CANCELED':
        return htmx_error("This session has been canceled and cannot be rescheduled. Please book a new session.")
        
    if booking.status == 'COMPLETED':
        return htmx_error("Cannot reschedule a completed session.")

    new_start_time_str = request.POST.get('new_start_time')

    if not new_start_time_str:
        return htmx_error("Please select a new time.")
    else:
        try:
            # Handle standard ISO format from code or browser
            if 'T' in new_start_time_str:
                new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
            else:
                new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%d %H:%M')
                
            new_start_time = timezone.make_aware(new_start_time)

            # --- 2. Safe Session Length Lookup (Fixes Free Session Crash) ---
            if booking.enrollment:
                session_length = booking.enrollment.offering.session_length_minutes
            else:
                # Fallback for Free/Direct sessions: use existing duration
                session_length = booking.get_duration_minutes() or 60

            # Use BookingService to respect Google Calendar busy slots
            available_slots = BookingService.get_slots_for_coach(
                booking.coach, new_start_time.date(), session_length
            )
            
            is_available = False
            for slot in available_slots:
                 slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
                 if slot_aware == new_start_time:
                     is_available = True
                     break

            if not is_available:
                return htmx_error("That time slot is no longer available. Please choose another.")
            else:
                # Double check against local DB to prevent double booking
                if SessionBooking.objects.filter(
                    coach=booking.coach,
                    start_datetime=new_start_time,
                    status__in=['BOOKED', 'PENDING_PAYMENT', 'RESCHEDULED']
                ).exclude(id=booking.id).exists():
                    return htmx_error("This time slot has already been booked. Please select another time.")

                original_start_time = booking.start_datetime
                result = booking.reschedule(new_start_time)

                if result == 'LATE':
                    return htmx_error("Sessions cannot be rescheduled within 24 hours of the start time.")
                else:
                    messages.success(request, f"Session successfully rescheduled to {new_start_time.strftime('%B %d, %H:%M')}.")
                    
                    try:
                        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
                        # Format original start time for template since we can't pass datetime object
                        formatted_original_time = original_start_time.strftime('%A, %B %d, %Y, %I:%M %p %Z')
                        
                        send_transactional_email(
                            recipient_email=booking.client.email,
                            subject="Your Coaching Session Has Been Rescheduled",
                            template_name='emails/reschedule_confirmation.html',
                            context={
                                'user_id': booking.client.pk,
                                'booking_id': booking.pk,
                                'original_start_time': formatted_original_time,
                                'dashboard_url': dashboard_url,
                            }
                        )

                        send_transactional_email(
                            recipient_email=booking.coach.user.email,
                            subject=f"Session Rescheduled by {booking.client.get_full_name()}",
                            template_name='emails/coach_reschedule_notification.html',
                            context={
                                'coach_id': booking.coach.pk,
                                'client_id': booking.client.pk,
                                'booking_id': booking.pk,
                                'original_start_time': formatted_original_time,
                                'dashboard_url': dashboard_url,
                            }
                        )
                    except Exception as e:
                        logger.error(f"CRITICAL: Reschedule for booking {booking.id} succeeded but failed to send emails. Error: {e}")

        except ValueError:
            return htmx_error("Invalid date format.")
        except Exception as e:
            logger.error(f"Reschedule Error: {e}", exc_info=True)
            return htmx_error(f"An error occurred: {e}")

    response = HttpResponse(status=204)
    response['HX-Redirect'] = reverse('accounts:account_profile')
    return response

@login_required
@require_POST
def apply_for_free_session(request):
    client = request.user
    coach_id = request.POST.get('coach_id')
    coach_instance = get_object_or_404(CoachProfile, id=coach_id)

    # Check for an existing, non-redeemed, non-expired offer with this specific coach
    existing_offer = OneSessionFreeOffer.objects.filter(
        client=client,
        coach=coach_instance,
        is_redeemed=False
    ).filter(
        Q(redemption_deadline__isnull=True) | Q(redemption_deadline__gt=timezone.now())
    ).first()

    if existing_offer:
        if existing_offer.is_approved:
            message = 'You already have an approved free session with this coach. Please book it from your profile.'
        else:
            message = 'You already have a pending request with this coach. They will review it shortly.'
        return render(request, 'coaching_booking/partials/free_session_status.html', {
            'status': 'pending',
            'message': message
        })

    # Create a new offer since no active one exists for this coach
    OneSessionFreeOffer.objects.create(
        client=client,
        coach=coach_instance,
        is_approved=False, 
        is_redeemed=False
    )
    
    return render(request, 'coaching_booking/partials/free_session_status.html', {
        'status': 'success', 
        'message': 'Request submitted! The coach will review it shortly.'
    })

@login_required
def profile_book_session_partial(request):
    user_offerings = ClientOfferingEnrollment.objects.filter(
        client=request.user,
        remaining_sessions__gt=0,
        is_active=True
    ).filter(
        Q(expiration_date__gte=timezone.now()) | Q(expiration_date__isnull=True)
    ).select_related('offering')

    free_offers = OneSessionFreeOffer.objects.filter(
        client=request.user,
        is_approved=True,
        is_redeemed=False,
        redemption_deadline__gte=timezone.now()
    ).select_related('coach__user')

    coaches = CoachProfile.objects.filter(
        # Only show coaches who are available for booking
        user__is_active=True,
        is_available_for_new_clients=True
    ).select_related('user')
    
    today = timezone.now().date()

    # Add an empty div for HTMX error swapping
    # <div id="booking-errors"></div>

    context = {
        # This partial is used for booking, so it's part of the 'book' tab
        'user_offerings': user_offerings,
        'free_offers': free_offers,
        'coaches': coaches,
        'initial_year': today.year,
        'initial_month': today.month,
        'selected_enrollment_id': '', 
        'selected_coach_id': '',      
        'selected_free_offer_id': '',
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

        client_context = {
            'client_id': free_offer.client.pk,
            'coach_id': coach_profile.pk,
            'offer_id': free_offer.pk,
            'dashboard_url': request.build_absolute_uri(reverse('accounts:account_profile'))
        }
        send_transactional_email(
            recipient_email=free_offer.client.email,
            subject=f"Your Free Session with {coach_profile.user.get_full_name()} is Approved!",
            template_name='emails/client_free_session_approved.html',
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
@require_POST
def coach_deny_free_session(request):
    offer_id = request.POST.get('offer_id')
    
    try:
        coach_profile = request.user.coach_profile
    except CoachProfile.DoesNotExist:
        messages.error(request, "You are not a coach.")
        return HttpResponse(status=403)

    free_offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)

    if free_offer.coach != coach_profile:
        messages.error(request, "You cannot manage this request.")
        return HttpResponse(status=403)

    free_offer.delete()

    messages.info(request, "Taster session request denied.")
    
    response = HttpResponse(status=200)
    response['HX-Trigger'] = 'refreshProfile' 
    return response

@login_required
def check_payment_status(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if booking.status == 'BOOKED': # Maps to CONFIRMED
        messages.success(request, "Payment confirmed! Your session is booked.")
        response = HttpResponse(status=200)
        response['HX-Redirect'] = reverse('accounts:account_profile')
        return response
    else:
        # Keep polling (return the same spinner div)
        return render(request, 'coaching_booking/partials/spinner.html', {'booking': booking})

@login_required
def get_booking_calendar(request):
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')
    reschedule_booking_id = request.GET.get('reschedule_booking_id')
    
    session_length = 60 # Default
    coach = None

    # --- 1. Reschedule Context Logic (Fixes Free Sessions) ---
    if reschedule_booking_id:
        try:
            # If rescheduling, derive context from the booking
            booking = SessionBooking.objects.get(id=reschedule_booking_id, client=request.user)
            coach = booking.coach
            coach_id = coach.id
            # Use the existing session duration
            session_length = booking.get_duration_minutes() or 60
        except SessionBooking.DoesNotExist:
            pass

    # --- 2. Standard Booking Context Logic ---
    if not coach and coach_id:
        coach = get_object_or_404(CoachProfile, id=coach_id)

    # --- 3. Validate Inputs ---
    # We allow missing enrollment_id IF we are rescheduling
    if not coach or (not enrollment_id and not reschedule_booking_id):
        return HttpResponse(
            '<div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center h-full flex flex-col justify-center items-center">'
            '<p class="text-gray-500 font-medium">Select an Offering and a Coach to view availability.</p>'
            '</div>'
        )

    # Determine Session Length for Standard Enrollment
    if not reschedule_booking_id and enrollment_id:
        if str(enrollment_id).startswith('free_'):
            session_length = 60 
        else:
            try:
                enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
                session_length = enrollment.offering.session_length_minutes
            except ClientOfferingEnrollment.DoesNotExist:
                pass

    try:
        year = int(request.GET.get('year', timezone.now().year))
        month = int(request.GET.get('month', timezone.now().month))
    except ValueError:
        year = timezone.now().year
        month = timezone.now().month

    # Get Timezone from Cookie
    user_tz = request.COOKIES.get('USER_TIMEZONE', 'UTC')

    # Call Service
    calendar_data = BookingService.get_month_schedule(
        coach, year, month, user_tz, session_length
    )

    # Convert the flat list of days into a list of weeks (7 days per week)
    calendar_rows = [calendar_data[i:i+7] for i in range(0, len(calendar_data), 7)]

    # Navigation Logic
    current_date = date(year, month, 1)
    
    # Disable 'Prev' if we are at the start of the current real month
    now_date = timezone.now().date()
    real_current_month_start = date(now_date.year, now_date.month, 1)
    disable_prev = current_date <= real_current_month_start
    is_current_month_view = (current_date.year == now_date.year and current_date.month == now_date.month)

    def get_month_link(d):
        return {'month': d.month, 'year': d.year}

    prev_date = current_date - timedelta(days=1)
    # Logic to get next month safely
    if month == 12:
        next_date = date(year + 1, 1, 1)
    else:
        next_date = date(year, month + 1, 1)

    context = {
        'calendar_rows': calendar_rows,
        'current_year': year,
        'current_month': month,
        'current_month_name': current_date.strftime('%B'),
        'prev_month': prev_date.month,
        'prev_year': prev_date.year,
        'next_month': next_date.month,
        'next_year': next_date.year,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id, # Can be "free_X" or normal ID
        'coach': coach, # Pass the object, not just ID
        'disable_prev': disable_prev,
        'is_current_month_view': is_current_month_view,
        'reschedule_booking_id': reschedule_booking_id,
    }
    return render(request, 'coaching_booking/partials/_calendar_widget.html', context)

@login_required
def confirm_booking_modal(request):
    """
    Renders the slide-over form when a user clicks a slot.
    """
    slot_iso = request.GET.get('time') # UTC ISO string
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')
    workshop_id = request.GET.get('workshop_id')
    
    # We pass these back to the form so the POST request has context
    context = {
        'slot_iso': slot_iso,
        'coach_id': coach_id,
        'enrollment_id': enrollment_id,
        'workshop_id': workshop_id,
    }
    
    # Optional: Pre-fetch data to show nice summary in the modal
    if slot_iso:
        try:
            dt = datetime.fromisoformat(slot_iso)
            context['pretty_time'] = dt.strftime('%B %d, %I:%M %p')
        except ValueError:
            pass

    return render(request, 'coaching_booking/partials/booking_form.html', context)

@login_required
def confirm_reschedule_modal(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id, client=request.user)
    new_start_time_str = request.GET.get('new_start_time')
    
    try:
        new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
        if timezone.is_naive(new_start_time):
            new_start_time = timezone.make_aware(new_start_time)
    except (ValueError, TypeError):
        return HttpResponse("Invalid time format", status=400)

    context = {
        'booking': booking,
        'new_start_time': new_start_time,
        'new_start_time_iso': new_start_time_str,
    }
    return render(request, 'coaching_booking/partials/reschedule_confirmation_modal.html', context)

@login_required
def get_daily_slots(request):
    date_str = request.GET.get('date')
    coach_id = request.GET.get('coach_id')
    enrollment_id_param = request.GET.get('enrollment_id')
    reschedule_booking_id = request.GET.get('reschedule_booking_id')

    context = {
        'coach_id': coach_id,
        'enrollment_id': '', # Default empty
        'free_offer_id': '', # Default empty
        'selected_date': None,
        'available_slots': [],
        'error_message': None,
        'reschedule_booking_id': reschedule_booking_id,
    }

    if not date_str or not coach_id:
        context['error_message'] = 'Please select a date and coach.'
        return render(request, 'coaching_booking/partials/available_slots.html', context)

    if not enrollment_id_param and not reschedule_booking_id:
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
        
        # FIX 2: Handle Rescheduling Context specifically
        if reschedule_booking_id:
            # If rescheduling, we derive session length from the existing booking
            # We do NOT require enrollment_id_param here
            booking = SessionBooking.objects.get(id=reschedule_booking_id, client=request.user)
            session_length = booking.get_duration_minutes() or 60
            
            # If enrollment_id happens to be passed, we can preserve it, but it's optional
            if enrollment_id_param and not str(enrollment_id_param).startswith('free_'):
                context['enrollment_id'] = enrollment_id_param

        # Handle "free_X" enrollment ID
        elif str(enrollment_id_param).startswith('free_'):
            free_id = str(enrollment_id_param).split('_')[1]
            free_offer = OneSessionFreeOffer.objects.get(id=free_id, client=request.user)
            
            # Check for Coach Mismatch
            if int(coach_id) != free_offer.coach.id:
                 context['error_message'] = "The selected coach does not match the approved free offer."
                 return render(request, 'coaching_booking/partials/available_slots.html', context)

            session_length = 60 
            context['free_offer_id'] = free_id
            context['enrollment_id'] = ''
            
        # Handle Standard Enrollment ID
        else:
            enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id_param, client=request.user)
            session_length = enrollment.offering.session_length_minutes
            context['enrollment_id'] = enrollment_id_param
            context['free_offer_id'] = ''
        
        available_slots = BookingService.get_slots_for_coach(
            coach_profile,
            selected_date,
            session_length
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

    except (ValueError, CoachProfile.DoesNotExist, ClientOfferingEnrollment.DoesNotExist, OneSessionFreeOffer.DoesNotExist, SessionBooking.DoesNotExist):
        context['error_message'] = 'Invalid request data or enrollment not found.'
    except Exception as e:
        context['error_message'] = f'Error fetching slots: {str(e)}'

    return render(request, 'coaching_booking/partials/available_slots.html', context)