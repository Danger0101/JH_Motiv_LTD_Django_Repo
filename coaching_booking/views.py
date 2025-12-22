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
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseForbidden
import stripe
from django.contrib.auth import login
from django.utils.crypto import get_random_string
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.core.paginator import Paginator

from core.email_utils import send_transactional_email
from payments.models import CoachingOrder
from .models import ClientOfferingEnrollment, SessionBooking, OneSessionFreeOffer
from accounts.models import CoachProfile, MarketingPreference
from coaching_availability.utils import get_coach_available_slots
from coaching_core.models import Offering, Workshop
from coaching_client.models import ContentPage
from cart.utils import get_or_create_cart, get_cart_summary_data
from facts.models import Fact
from .services import BookingService
from django.core.exceptions import ValidationError
from accounts.models import User

logger = logging.getLogger(__name__)
BOOKING_WINDOW_DAYS = 90
stripe.api_key = settings.STRIPE_SECRET_KEY

class CoachLandingView(TemplateView):
    template_name = "coaching_booking/coach_landing.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        coaches = CoachProfile.objects.filter(user__is_active=True, is_available_for_new_clients=True).select_related('user')
        offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches__user')
        workshops = Workshop.objects.filter(active_status=True)
        knowledge_pages = ContentPage.objects.filter(is_published=True).order_by('title')[:3]
        facts = Fact.objects.all()
        KNOWLEDGE_CATEGORIES = [('all', 'Business Coaches')]
        cart = get_or_create_cart(self.request)
        
        upcoming_workshops = Workshop.objects.filter(
            active_status=True,
            date__gte=timezone.now()
        ).order_by('date')[:3]

        context.update({
            'coaches': coaches,
            'offerings': offerings,
            'workshops': workshops,
            'knowledge_pages': knowledge_pages,
            'facts': facts,
            'knowledge_categories': KNOWLEDGE_CATEGORIES[1:],
            'page_summary_text': "Welcome to our coaching services!",
            'upcoming_workshops': upcoming_workshops,
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
            
            # --- GCAL SYNC HOOK ---
            # If you have a GCal service, trigger the sync here to ensure the meeting link is generated immediately.
            # try:
            #     from gcal.utils import sync_booking_to_gcal
            #     sync_booking_to_gcal(booking)
            # except ImportError:
            #     pass
            
            # Email is now handled by signals.py -> tasks.py asynchronously
            msg = f"Session confirmed for {booking.start_datetime.strftime('%B %d, %Y at %I:%M %p')}. A confirmation email has been sent."
            messages.success(request, msg)
            response = HttpResponse(status=204)
            response['HX-Trigger'] = json.dumps({
                'refreshBookings': True,
                'refreshOfferings': True,
                'showToast': {'message': msg, 'type': 'success'}
            })
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
    booking = get_object_or_404(SessionBooking, id=booking_id)
    
    is_client = booking.client == request.user
    is_coach = booking.coach.user == request.user
    
    if not (is_client or is_coach):
        return HttpResponseForbidden("You are not authorized to cancel this session.")

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
    elif not is_refunded:
        client_msg = "Your session was canceled. As this was within 24 hours of the start time, the session credit was forfeited per our Terms of Service."

    msg = ""
    toast_type = "success"

    if is_client:
        if is_refunded and booking.enrollment:
            msg = "Session canceled successfully. Your credit has been restored."
            messages.success(request, msg)
        else:
            msg = "Session canceled. The credit was forfeited due to late cancellation."
            messages.warning(request, msg)
            toast_type = "warning"
    elif is_coach:
        msg = "Session canceled successfully. The client has been notified."
        messages.success(request, msg)
        
        # Override client message for email context if coach canceled
        client_msg = f"Coach {coach.user.get_full_name()} has canceled this session. Your credit has been restored."

    try:
        # Format dates for email context
        original_date_str = booking.start_datetime.strftime("%A, %B %d, %Y")
        original_time_start_str = booking.start_datetime.strftime("%I:%M %p UTC")
        original_time_end_str = booking.end_datetime.strftime("%I:%M %p UTC")

        dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
        
        # Email to Client
        send_transactional_email(
            recipient_email=client.email,
            subject=f"Session Canceled by Coach {coach.user.get_full_name()}" if is_coach else "Your Coaching Session Has Been Canceled",
            template_name='emails/cancellation_confirmation.html',
            context={
                'user_id': client.pk,
                'booking_id': booking.pk,
                'cancellation_message': client_msg,
                'dashboard_url': dashboard_url,
                'original_date': original_date_str,
                'original_time': original_time_start_str,
                'original_time_start': original_time_start_str,
                'original_time_end': original_time_end_str,
            }
        )

        # Email to Coach (only if client canceled)
        if is_client:
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
                    'original_time': original_time_start_str,
                    'original_time_start': original_time_start_str,
                    'original_time_end': original_time_end_str,
                }
            )
    except Exception as e:
        logger.error(f"CRITICAL: Cancellation for booking {booking.id} succeeded but failed to send emails. Error: {e}")

    # Redirect to profile to refresh the dashboard
    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({
        'refreshBookings': True,
        'refreshOfferings': True,
        'showToast': {'message': msg, 'type': toast_type}
    })
    return response

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
        
    # Determine allowed coaches for this reschedule
    coaches = [booking.coach]
    if booking.enrollment and not booking.enrollment.coach:
         coaches = booking.enrollment.offering.coaches.filter(
            user__is_active=True,
            is_available_for_new_clients=True
        )
    
    today = timezone.now().date()
    
    return render(request, 'coaching_booking/profile_book_session.html', {
        'reschedule_booking_id': booking.id,
        'booking': booking,
        'coaches': coaches,
        'initial_year': today.year,
        'initial_month': today.month,
        'selected_coach_id': booking.coach.id,
        'user_offerings': [],
        'free_offers': [],
        'selected_enrollment_id': booking.enrollment.id if booking.enrollment else '',
        'selected_free_offer_id': '',
    })

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
    new_coach_id = request.POST.get('coach_id')

    if not new_start_time_str:
        return htmx_error("Please select a new time.")

    try:
        original_start_time = booking.start_datetime
        
        # Use Service for robust rescheduling
        BookingService.reschedule_booking(booking, new_start_time_str, new_coach_id)
        
        # Success Logic
        new_start_time = booking.start_datetime
        msg = f"Session successfully rescheduled to {new_start_time.strftime('%B %d, %H:%M')}."
        messages.success(request, msg)
        
        try:
            dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
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

    except ValidationError as e:
        return htmx_error(e.messages[0] if hasattr(e, 'messages') else str(e))
    except Exception as e:
        logger.error(f"Reschedule Error: {e}", exc_info=True)
        return htmx_error(f"An error occurred: {str(e)}")

    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({
        'refreshBookings': True,
        'showToast': {'message': msg, 'type': 'success'}
    })
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
        status__in=['PENDING', 'APPROVED']
    ).filter(
        Q(redemption_deadline__isnull=True) | Q(redemption_deadline__gt=timezone.now())
    ).first()

    if existing_offer:
        if existing_offer.status == 'APPROVED':
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
        status='PENDING'
    )
    
    return render(request, 'coaching_booking/partials/free_session_status.html', {
        'status': 'success', 
        'message': 'Request submitted! The coach will review it shortly.'
    })

@login_required
@require_POST
def request_taster(request, offering_id):
    offering = get_object_or_404(Offering, id=offering_id)
    
    if not offering.coach:
         return HttpResponse('<div class="text-red-600 text-sm mt-2">This offering has no assigned coach.</div>')

    # Check for existing pending/active offers
    existing = OneSessionFreeOffer.objects.filter(
        client=request.user,
        coach=offering.coach,
        status__in=['PENDING', 'APPROVED']
    ).exists()
    
    if existing:
        return HttpResponse('<button disabled class="w-full bg-gray-100 text-gray-400 font-bold py-2 px-4 rounded-lg border border-gray-200 cursor-not-allowed">Request Pending / Active</button>')

    # Create the offer
    OneSessionFreeOffer.objects.create(
        client=request.user,
        coach=offering.coach,
        offering=offering,
        status='PENDING'
    )
    
    return HttpResponse('<button disabled class="w-full bg-indigo-50 text-indigo-400 font-bold py-2 px-4 rounded-lg border border-indigo-100 cursor-not-allowed">Request Sent</button>')

@login_required
def book_taster_session(request, offer_id):
    # Retrieve the specific approved offer
    offer = get_object_or_404(OneSessionFreeOffer, id=offer_id, client=request.user, status='APPROVED')
    
    if request.method == "POST":
        slot_str = request.POST.get('slot')
        
        try:
            if slot_str:
                start_dt = datetime.fromisoformat(slot_str)
                if timezone.is_naive(start_dt):
                    start_dt = timezone.make_aware(start_dt)
                
                # Create a confirmed booking with zero payment
                booking = SessionBooking.objects.create(
                    client=request.user,
                    coach=offer.coach,
                    offering=offer.offering,
                    start_datetime=start_dt,
                    status='BOOKED',
                    amount_paid=0
                )
                # Mark the taster session as used to prevent multiple bookings
                offer.status = 'USED'
                offer.session = booking
                offer.save()
                
                messages.success(request, "Free taster session booked successfully!")
            else:
                messages.error(request, "No time slot selected.")

        except ValueError:
            messages.error(request, "Invalid time slot selected.")
            
        return redirect('accounts:account_profile')
    
    return redirect('accounts:account_profile') # Redirect on GET

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
        status='APPROVED',
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
        'selected_enrollment_id': request.GET.get('enrollment_id', ''), 
        'selected_coach_id': request.GET.get('coach_id', ''),      
        'selected_free_offer_id': request.GET.get('free_offer_id', ''),
    }
    return render(request, 'coaching_booking/profile_book_session.html', context)

@login_required
@require_POST
def approve_taster(request, offer_id):
    coach_user = request.user

    try:
        coach_profile = CoachProfile.objects.get(user=coach_user)
    except CoachProfile.DoesNotExist:
        messages.error(request, "You are not recognized as a coach.")
        return HttpResponse(status=403)

    free_offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)

    if free_offer.coach != coach_profile:
        messages.error(request, "You are not authorized to approve this offer.")
        return HttpResponse(status=403)

    if free_offer.status != 'PENDING':
        messages.info(request, "This offer is not pending approval.")
        return HttpResponse(f'<div hx-swap-oob="true" id="offer-{offer_id}"></div>')

    free_offer.status = 'APPROVED'
    free_offer.save()

    # client_context = { ... }
    # send_transactional_email(...)
    
    messages.success(request, f"Free session offer for {free_offer.client.get_full_name()} approved.")
    # HTMX will remove the element from the DOM on success
    return HttpResponse("")

@login_required
@require_POST
def decline_taster(request, offer_id):
    try:
        coach_profile = request.user.coach_profile
    except CoachProfile.DoesNotExist:
        messages.error(request, "You are not a coach.")
        return HttpResponse(status=403)

    free_offer = get_object_or_404(OneSessionFreeOffer, id=offer_id)

    if free_offer.coach != coach_profile:
        messages.error(request, "You cannot manage this request.")
        return HttpResponse(status=403)

    free_offer.status = 'DECLINED'
    free_offer.save()

    messages.info(request, "Taster session request denied.")
    
    # HTMX will remove the element from the DOM on success
    return HttpResponse("")

@login_required
def check_payment_status(request, booking_id):
    booking = get_object_or_404(SessionBooking, id=booking_id)
    if booking.status == 'BOOKED': # Maps to CONFIRMED
        msg = "Payment confirmed! Your session is booked."
        messages.success(request, msg)
        response = HttpResponse('<div class="text-center text-green-600 font-bold p-4">Payment Confirmed!</div>', status=200)
        response['HX-Trigger'] = json.dumps({
            'refreshBookings': True,
            'refreshOfferings': True,
            'showToast': {'message': msg, 'type': 'success'}
        })
        return response
    else:
        # Keep polling (return the same spinner div)
        return render(request, 'coaching_booking/partials/spinner.html', {'booking': booking})

def guest_access_view(request, token):
    user = get_object_or_404(User, billing_notes=token)
    
    user.is_active = True
    # Log them in automatically for this session
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    
    # Clear the token so the link only works once for "activation"
    user.billing_notes = ""
    user.save()
    
    messages.success(request, "Welcome! Please set a permanent password to secure your account.")
    return redirect('accounts:account_profile')

@login_required
def staff_create_guest_account(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Only staff can perform this action.")
    
    offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches__user')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        business_name = request.POST.get('business_name')
        
        if not email or not full_name:
            messages.error(request, "Email and Name are required.")
            return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

        user = User.objects.filter(Q(email=email) | Q(username=email)).first()
        random_password = None

        if not user:
            first_name = full_name.split(' ')[0]
            last_name = ' '.join(full_name.split(' ')[1:]) if ' ' in full_name else ''
            random_password = get_random_string(12)
            
            user = User.objects.create_user(
                username=email,
                email=email,
                password=random_password,
                first_name=first_name,
                last_name=last_name,
                business_name=business_name,
                is_active=False
            )
            MarketingPreference.objects.create(user=user, is_subscribed=False)
            
        elif business_name and not user.business_name:
            user.business_name = business_name
            user.save()
        
        guest_token = get_random_string(32)
        user.billing_notes = guest_token
        user.save()
        
        # Optional Enrollment
        offering_id = request.POST.get('offering_id')
        coach_id = request.POST.get('coach_id')
        enrolled_offering_name = None
        if offering_id:
            try:
                offering = Offering.objects.get(id=offering_id)
                
                # Validation: Ensure a coach is selected if the offering has multiple coaches
                if offering.coaches.count() > 1 and not coach_id:
                    messages.error(request, "Please select a coach for this offering.")
                    return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

                selected_coach = None
                if coach_id:
                    selected_coach = offering.coaches.filter(id=coach_id).first()

                ClientOfferingEnrollment.objects.create(
                    client=user,
                    offering=offering,
                    coach=selected_coach,
                    remaining_sessions=offering.total_number_of_sessions,
                    is_active=True
                )
                enrolled_offering_name = offering.name
            except Offering.DoesNotExist:
                pass
        
        access_url = request.build_absolute_uri(
            reverse('coaching_booking:guest_access', args=[guest_token])
        )
        
        context = {
            'site_name': getattr(settings, 'SITE_NAME', 'JH Motiv'),
            'access_url': access_url,
            'username': email,
            'password': random_password,
            'enrolled_offering_name': enrolled_offering_name,
            'is_new_account': bool(random_password)
        }
        
        try:
            send_transactional_email(
                recipient_email=email,
                subject=f"Welcome to {context['site_name']}",
                template_name='emails/guest_welcome.html',
                context=context
            )
        except Exception as e:
            messages.error(request, f"Error sending email: {e}")
        
        action_verb = "created" if random_password else "updated"
        messages.success(request, f"Guest account {action_verb} for {email}. Email sent.")
        return redirect('coaching_booking:staff_create_guest')
        
    return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

@login_required
@require_POST
def staff_send_password_reset(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Only staff can perform this action.")
    
    email = request.POST.get('email')
    offerings = Offering.objects.filter(active_status=True).prefetch_related('coaches__user')
    
    if not email:
        messages.error(request, "Email is required.")
        return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

    # Find user by email or username
    user = User.objects.filter(Q(email=email) | Q(username=email)).first()
    
    if user:
        # Use Django's built-in PasswordResetForm to generate the standard reset email
        form = PasswordResetForm({'email': user.email})
        if form.is_valid():
            try:
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                )
                messages.success(request, f"Password reset email sent to {user.email}.")
            except Exception as e:
                messages.error(request, f"Error sending password reset: {e}")
        else:
            messages.error(request, "Error generating password reset.")
    else:
        messages.error(request, f"No user found matching '{email}'.")
        
    return render(request, 'account/partials/staff/staff_create_guest.html', {'offerings': offerings})

@login_required
def recent_guests_widget(request):
    if not request.user.is_staff:
        return HttpResponseForbidden()
    
    q = request.GET.get('q', '')
    page = request.GET.get('page')
    status = request.GET.get('status', 'pending')
    
    guests_query = User.objects.all()
    
    # Filter by Status
    if status == 'pending':
        guests_query = guests_query.exclude(billing_notes='').exclude(billing_notes__isnull=True)
    elif status == 'active':
        guests_query = guests_query.filter(Q(billing_notes='') | Q(billing_notes__isnull=True))
        guests_query = guests_query.filter(is_staff=False)
    
    if q:
        guests_query = guests_query.filter(email__icontains=q)
    
    paginator = Paginator(guests_query.order_by('-date_joined'), 5)
    recent_guests = paginator.get_page(page)
    
    return render(request, 'account/partials/staff/_recent_guests.html', {
        'recent_guests': recent_guests,
        'q': q,
        'status': status
    })

@login_required
@require_POST
def resend_guest_invite(request, user_id):
    if not request.user.is_staff:
        return HttpResponseForbidden()
        
    user = get_object_or_404(User, id=user_id)
    
    if not user.billing_notes:
        return HttpResponse('<span class="text-xs text-gray-500">Active</span>')
        
    token = user.billing_notes
    access_url = request.build_absolute_uri(
        reverse('coaching_booking:guest_access', args=[token])
    )
    
    try:
        context = {
            'site_name': getattr(settings, 'SITE_NAME', 'JH Motiv'),
            'access_url': access_url,
            'username': user.email,
            'is_new_account': False
        }
        send_transactional_email(
            recipient_email=user.email,
            subject=f"Access Link for {context['site_name']}",
            template_name='emails/guest_welcome.html',
            context=context
        )
        
        user.last_invite_sent = timezone.now()
        user.save(update_fields=['last_invite_sent'])
        
        return HttpResponse('<span class="text-xs text-green-600 font-bold px-2">Sent!</span>')
    except Exception as e:
        logger.error(f"Failed to resend invite: {e}")
        return HttpResponse(f'<span class="text-xs text-red-600 font-bold px-2" title="{e}">Failed</span>')

@login_required
@require_POST
def delete_guest_account(request, user_id):
    if not request.user.is_staff:
        return HttpResponseForbidden()
        
    user = get_object_or_404(User, id=user_id)
    
    user.delete()
    
    return HttpResponse("")

def book_workshop(request, slug):
    workshop = get_object_or_404(Workshop, slug=slug)
    
    # 1. HANDLE POST REQUEST (Form Submission)
    if request.method == 'POST':
        # Get data
        email = request.POST.get('email')
        full_name = request.POST.get('full_name')
        business_name = request.POST.get('business_name')
        
        # Validation
        if not email or not full_name:
            messages.error(request, "Name and Email are required.")
            return redirect('coaching_core:workshop_detail', slug=slug)

        # 2. RESOLVE USER (Login or Create)
        user = None
        if request.user.is_authenticated:
            user = request.user
            # Update business name if missing
            if business_name and not user.business_name:
                user.business_name = business_name
                user.save()
        else:
            # Check if user exists
            existing_user = User.objects.filter(Q(email=email) | Q(username=email)).first()
            if existing_user:
                # OPTION B: Auto-link (Easier for User, requires trust)
                user = existing_user
                if business_name and not user.business_name:
                    user.business_name = business_name
                    user.save()
            else:
                # Create New Guest User
                first_name = full_name.split(' ')[0]
                last_name = ' '.join(full_name.split(' ')[1:]) if ' ' in full_name else ''
                random_password = get_random_string(12)
                
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=random_password,
                    first_name=first_name,
                    last_name=last_name,
                    business_name=business_name
                )
                
                # Generate a unique token for their "Guest Dashboard"
                guest_token = get_random_string(32)
                user.billing_notes = guest_token 
                user.save()

                # Auto-login the new user so they see their dashboard
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                access_url = request.build_absolute_uri(
                    reverse('coaching_booking:guest_access', args=[guest_token])
                )
                
                # Send Welcome Email with Password
                context = {
                    'site_name': getattr(settings, 'SITE_NAME', 'JH Motiv'),
                    'access_url': access_url,
                    'username': email,
                    'password': random_password,
                    'workshop_name': workshop.name,
                    'is_new_account': True
                }
                send_transactional_email(
                    recipient_email=email,
                    subject=f"Welcome to {context['site_name']}",
                    template_name='emails/guest_welcome.html',
                    context=context
                )

        # 3. CREATE BOOKING
        # Check for duplicates
        if SessionBooking.objects.filter(client=user, workshop=workshop).exists():
            messages.info(request, "You are already booked for this workshop!")
            return redirect('accounts:account_profile')

        if workshop.price == 0:
            # --- FREE FLOW ---
            start_dt = datetime.combine(workshop.date, workshop.start_time)
            if timezone.is_naive(start_dt):
                start_dt = timezone.make_aware(start_dt)

            booking = SessionBooking.objects.create(
                client=user,
                coach=workshop.coach,
                workshop=workshop,
                start_datetime=start_dt,
                status='BOOKED',
                amount_paid=0
            )
            
            # Send Confirmation
            BookingService.send_confirmation_emails(request, booking)
            
            messages.success(request, "Workshop booked successfully!")
            return redirect('accounts:account_profile')
            
        else:
            # --- PAID FLOW ---
            return redirect('payments:checkout_workshop', workshop_id=workshop.id)

    return redirect('coaching_core:workshop_detail', slug=slug)

@login_required
def get_booking_calendar(request):
    coach_id = request.GET.get('coach_id')
    enrollment_id = request.GET.get('enrollment_id')
    reschedule_booking_id = request.GET.get('reschedule_booking_id')
    
    session_length = 60 # Default
    coach = None
    slot_target_id = '#time-slots-column' # Default target

    # --- 1. Determine Context (Reschedule vs New Booking) ---
    if reschedule_booking_id:
        try:
            booking = SessionBooking.objects.get(id=reschedule_booking_id, client=request.user)
            session_length = booking.get_duration_minutes() or 60
            # slot_target_id = '#reschedule-slots-container' # Removed to match profile_book_session.html target
            
            # Default to booking coach if not explicitly changed
            if not coach_id:
                coach = booking.coach
                coach_id = coach.id
        except SessionBooking.DoesNotExist:
            pass
    
    elif enrollment_id:
        # Standard Booking
        if str(enrollment_id).startswith('free_'):
            session_length = 60 
        else:
            try:
                enrollment = ClientOfferingEnrollment.objects.get(id=enrollment_id, client=request.user)
                session_length = enrollment.offering.session_length_minutes
            except ClientOfferingEnrollment.DoesNotExist:
                pass

    # --- 2. Resolve Coach ---
    if not coach and coach_id:
        coach = get_object_or_404(CoachProfile, id=coach_id)

    # --- 3. Validate Inputs ---
    if not coach:
        return HttpResponse(
            '<div class="bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg p-8 text-center h-full flex flex-col justify-center items-center">'
            '<p class="text-gray-500 font-medium">Select an Offering and a Coach to view availability.</p>'
            '</div>'
        )

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
        'slot_target_id': slot_target_id,
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
    coach_id = request.GET.get('coach_id')
    
    try:
        # Handle ISO format (e.g. 2023-10-25T14:00:00Z)
        clean_time = new_start_time_str.replace('Z', '+00:00')
        dt = datetime.fromisoformat(clean_time)
        if timezone.is_naive(dt):
            new_start_time = timezone.make_aware(dt)
        else:
            new_start_time = dt
    except ValueError:
        try:
            new_start_time = datetime.strptime(new_start_time_str, '%Y-%m-%dT%H:%M')
            if timezone.is_naive(new_start_time):
                new_start_time = timezone.make_aware(new_start_time)
        except (ValueError, TypeError):
            return HttpResponse("Invalid time format", status=400)

    new_coach = booking.coach
    if coach_id and int(coach_id) != booking.coach.id:
        new_coach = get_object_or_404(CoachProfile, id=coach_id)

    # Calculate end time for display
    if booking.enrollment:
        session_length = booking.enrollment.offering.session_length_minutes
    else:
        session_length = booking.get_duration_minutes() or 60
    new_end_time = new_start_time + timedelta(minutes=session_length)

    context = {
        'booking': booking,
        'new_start_time': new_start_time,
        'new_end_time': new_end_time,
        'new_start_time_iso': new_start_time_str,
        'new_coach': new_coach,
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
            free_offer = OneSessionFreeOffer.objects.get(id=free_id, client=request.user, status='APPROVED')
            
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