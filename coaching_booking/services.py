from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from datetime import datetime, timedelta
import calendar
import pytz
import logging
import stripe
from django.conf import settings
from django.core.cache import cache
from django.urls import reverse
from django.utils.crypto import get_random_string

from .models import SessionBooking, ClientOfferingEnrollment, OneSessionFreeOffer, CoachBusySlot, SessionCoverageRequest
from coaching_core.models import CoachProfile, Workshop
from coaching_availability.utils import get_coach_available_slots
from accounts.models import User, MarketingPreference
from core.email_utils import send_transactional_email

logger = logging.getLogger(__name__)
BOOKING_WINDOW_DAYS = 90

stripe.api_key = settings.STRIPE_SECRET_KEY

class BookingService:
    
    @staticmethod
    def get_slots_for_coach(coach, date_obj, session_length=60):
        """
        Returns list of available start_times for a specific date.
        Wraps the existing availability utility.
        """
        raw_slots = get_coach_available_slots(
            coach,
            date_obj,
            date_obj,
            session_length,
            offering_type='one_on_one'
        )
        
        # Filter out slots that overlap with Google Calendar Busy Slots
        # Fetch busy slots for the day
        day_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
        day_end = day_start + timedelta(days=1)
        
        busy_slots = CoachBusySlot.objects.filter(
            coach=coach,
            start_time__lt=day_end,
            end_time__gt=day_start
        )
        
        # FIX: Also fetch existing internal bookings to prevent double-booking
        existing_bookings = SessionBooking.objects.filter(
            coach=coach,
            status__in=['BOOKED', 'PENDING_PAYMENT', 'RESCHEDULED', 'COMPLETED'],
            start_datetime__lt=day_end,
            end_datetime__gt=day_start
        )
        
        valid_slots = []
        session_delta = timedelta(minutes=session_length)
        
        for slot in raw_slots:
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            slot_end = slot_aware + session_delta
            
            is_blocked = False
            for busy in busy_slots:
                # Overlap Logic: (StartA < EndB) and (EndA > StartB)
                if slot_aware < busy.end_time and slot_end > busy.start_time:
                    is_blocked = True
                    break
            
            # FIX: Check Internal Bookings
            if not is_blocked:
                for booking in existing_bookings:
                    if slot_aware < booking.end_datetime and slot_end > booking.start_datetime:
                        is_blocked = True
                        break
            
            if not is_blocked:
                valid_slots.append(slot)
                
        return valid_slots

    @staticmethod
    def get_month_schedule(coach, year, month, user_timezone_str='UTC', session_length=60):
        """
        Generates a calendar payload for the view.
        Returns a list of days, each containing status and slots.
        """
        # 1. Generate Cache Key
        # We use a separate cache key for the version since we can't modify the Coach model
        version_key = f"coach_calendar_version_{coach.id}"
        version = cache.get_or_set(version_key, 1, timeout=None)
        cache_key = f"calendar_{coach.id}_v{version}_{year}_{month}_{user_timezone_str}_{session_length}"
        
        cached_data = cache.get(cache_key)
        if cached_data:
            return cached_data

        try:
            user_tz = pytz.timezone(user_timezone_str)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.UTC

        # 1. Calculate Date Range for the Grid (Month + Padding if needed)
        # We use calendar to get the full weeks to render a proper grid
        cal = calendar.Calendar(firstweekday=0) # Monday start
        month_dates_grid = cal.monthdatescalendar(year, month) # List of weeks, each week is list of date objects
        
        # Flatten the grid to get start and end for the query
        flat_dates = [d for week in month_dates_grid for d in week]
        start_date = flat_dates[0]
        end_date = flat_dates[-1]

        # 2. Fetch Available Slots (UTC)
        # We use the existing utility which handles AvailabilityBlocks and Bookings (Exceptions)
        available_slots_utc = get_coach_available_slots(
            coach,
            start_date,
            end_date,
            session_length,
            offering_type='one_on_one'
        )
        
        # Fetch Busy Slots for the whole range
        # Convert dates to aware datetimes to avoid RuntimeWarning about naive datetimes
        start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

        busy_slots = CoachBusySlot.objects.filter(
            coach=coach,
            start_time__lt=end_dt,
            end_time__gt=start_dt
        )
        
        # FIX: Also fetch existing internal bookings to prevent double-booking
        existing_bookings = SessionBooking.objects.filter(
            coach=coach,
            status__in=['BOOKED', 'PENDING_PAYMENT', 'RESCHEDULED', 'COMPLETED'],
            start_datetime__lt=end_dt,
            end_datetime__gt=start_dt
        )
        
        session_delta = timedelta(minutes=session_length)

        # 3. Bucket Slots by Date (in User TZ)
        slots_by_date = {}
        for slot in available_slots_utc:
            # slot is a datetime object in UTC (or aware)
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            slot_end = slot_aware + session_delta
            
            # Check against busy slots
            is_blocked = False
            for busy in busy_slots:
                if slot_aware < busy.end_time and slot_end > busy.start_time:
                    is_blocked = True
                    break
            
            if not is_blocked:
                for booking in existing_bookings:
                    if slot_aware < booking.end_datetime and slot_end > booking.start_datetime:
                        is_blocked = True
                        break
            
            if is_blocked:
                continue
            
            # Convert to User Local Time
            local_dt = slot_aware.astimezone(user_tz)
            day_key = local_dt.date()
            
            if day_key not in slots_by_date:
                slots_by_date[day_key] = []
            
            slots_by_date[day_key].append({
                'type': '1ON1',
                'display_time': local_dt.strftime('%I:%M %p'), # 09:00 AM
                'iso_value': slot_aware.isoformat(), # Keep UTC ISO for backend submission
                'available': True
            })

        # 4. Fetch Workshops for this Month
        workshops = Workshop.objects.filter(
            coach=coach,
            date__gte=start_date,
            date__lte=end_date
        ).annotate(
            booked_count=Count('bookings', filter=Q(bookings__status='BOOKED')),
            total_held_count=Count('bookings', filter=Q(bookings__status__in=['BOOKED', 'PENDING_PAYMENT']))
        )

        # 5. Merge Workshops into the Schedule
        for ws in workshops:
            # Convert to User Local Time
            dt = datetime.combine(ws.date, ws.start_time)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            local_start = dt.astimezone(user_tz)
            day_key = local_start.date()
            
            # Determine Status
            is_held_full = ws.total_held_count >= ws.total_attendees
            
            booking_status = 'AVAILABLE'
            if ws.booked_count >= ws.total_attendees:
                booking_status = 'FULL'
            elif is_held_full:
                booking_status = 'PENDING_FULL'
            
            workshop_slot = {
                'type': 'WORKSHOP',
                'id': ws.id,
                'title': ws.name,
                'display_time': local_start.strftime('%I:%M %p'),
                'iso_value': dt.isoformat(),
                'available': not is_held_full,
                'spots_left': ws.remaining_spaces,
                'booking_status': booking_status
            }

            if day_key not in slots_by_date:
                slots_by_date[day_key] = []
            
            slots_by_date[day_key].append(workshop_slot)
            # Sort slots by time so they appear in order
            slots_by_date[day_key].sort(key=lambda x: x['iso_value'])

        # 6. Construct the Grid Data
        schedule = []
        today = timezone.now().date()
        for d in flat_dates:
            day_slots = slots_by_date.get(d, [])
            has_available = any(s['available'] for s in day_slots)
            is_fully_booked = len(day_slots) > 0 and not has_available

            schedule.append({
                'date': d,
                'number': d.day,
                'is_past': d < today,
                'is_today': d == today,
                'is_current_month': d.month == month,
                'slots': day_slots,
                'has_available': has_available,
                'is_fully_booked': is_fully_booked
            })
            
        # 4. Save to Cache (e.g., for 1 hour)
        cache.set(cache_key, schedule, timeout=60*60)
        
        return schedule

    @staticmethod
    @transaction.atomic
    def create_booking(booking_data, user=None, provider_coach=None):
        """
        Universal booking creator. Handles Atomicity, Guest logic, and Race Conditions.
        provider_coach: Optional CoachProfile override (for coverage).
        """
        # 1. Parse Start Time
        start_time_input = booking_data.get('start_time')
        if not start_time_input:
            raise ValidationError("Please select a start time.")

        if isinstance(start_time_input, str):
            try:
                start_datetime_naive = datetime.strptime(start_time_input, '%Y-%m-%d %H:%M')
                start_datetime_obj = timezone.make_aware(start_datetime_naive)
            except ValueError:
                clean_time = start_time_input.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_time)
                if timezone.is_naive(dt):
                    start_datetime_obj = timezone.make_aware(dt)
                else:
                    start_datetime_obj = dt
        else:
            start_datetime_obj = start_time_input

        # Basic Time Validation
        now = timezone.now()
        if start_datetime_obj < now:
            raise ValidationError("Cannot book a session in the past.")
        if start_datetime_obj > now + timedelta(days=BOOKING_WINDOW_DAYS):
            raise ValidationError(f"Cannot book more than {BOOKING_WINDOW_DAYS} days in advance.")

        # --- GUEST HANDLING: Create Shadow User if needed ---
        guest_email = booking_data.get('email')
        if not user and guest_email:
            # Check if user exists (match views.py logic)
            user = User.objects.filter(Q(email=guest_email) | Q(username=guest_email)).first()
            if not user:
                # Create Shadow User
                full_name = booking_data.get('name', 'Guest')
                first_name = full_name.split(' ')[0]
                last_name = ' '.join(full_name.split(' ')[1:]) if ' ' in full_name else ''
                
                user = User.objects.create_user(
                    username=guest_email,
                    email=guest_email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=False
                )
                user.set_unusable_password()
                user.billing_notes = get_random_string(32) # Guest Token
                user.save()
                MarketingPreference.objects.create(user=user, is_subscribed=False)

        # 2. Determine Booking Type (Workshop vs 1-on-1)
        if booking_data.get('workshop_id'):
            result = BookingService._create_workshop_booking(booking_data, user, start_datetime_obj)
        else:
            # Pass provider_coach to 1on1 logic
            result = BookingService._create_1on1_booking(booking_data, user, start_datetime_obj, provider_coach)
            
        return result

    @staticmethod
    def _create_workshop_booking(booking_data, user, start_datetime_obj):
        workshop_id = booking_data['workshop_id']
        
        # Lock the workshop row to prevent overbooking (Race Condition Check)
        workshop = Workshop.objects.select_for_update().get(id=workshop_id)
        
        # Check Capacity
        current_bookings = workshop.bookings.filter(status__in=['BOOKED', 'PENDING_PAYMENT']).count()
        if current_bookings >= workshop.total_attendees:
            raise ValidationError("This workshop is fully booked.")

        # Guest Logic
        guest_email = booking_data.get('email', '')
        guest_name = booking_data.get('name', '')
        
        if not user and not guest_email:
            raise ValidationError("User or Guest Email is required.")

        # Determine Price (Assuming Workshop has a price field, defaulting to 0 if not found/accessible)
        price_in_cents = int(getattr(workshop, 'price', 0) * 100)
        product_name = f"Workshop: {workshop.name}"
        
        status = 'BOOKED' if price_in_cents == 0 else 'PENDING_PAYMENT'

        ws_start = datetime.combine(workshop.date, workshop.start_time)
        ws_end = datetime.combine(workshop.date, workshop.end_time)
        if timezone.is_naive(ws_start):
            ws_start = timezone.make_aware(ws_start)
        if timezone.is_naive(ws_end):
            ws_end = timezone.make_aware(ws_end)

        booking = SessionBooking.objects.create(
            workshop=workshop,
            coach=workshop.coach,
            client=user,
            guest_email=guest_email,
            guest_name=guest_name,
            start_datetime=ws_start,
            end_datetime=ws_end,
            status=status
        )
        
        if price_in_cents == 0:
            return {'type': 'confirmed', 'booking': booking}
            
        # Create Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            customer_email=guest_email or (user.email if user else None),
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': product_name},
                    'unit_amount': price_in_cents,
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=f"{settings.SITE_URL}/booking/verify-payment/{booking.id}/",
            cancel_url=f"{settings.SITE_URL}/booking/cancel-payment/{booking.id}/",
            metadata={
                'booking_id': booking.id,
                'type': 'coaching_booking'
            }
        )
        
        booking.stripe_checkout_session_id = checkout_session.id
        booking.save()
        
        return {'type': 'checkout', 'url': checkout_session.url, 'booking_id': booking.id}

    @staticmethod
    @transaction.atomic
    def reschedule_booking(booking, new_start_time_input, new_coach_id=None):
        """
        Reschedules an existing booking to a new time and optionally a new coach.
        """
        # 1. Parse Start Time
        if isinstance(new_start_time_input, str):
            try:
                # Handle ISO format (e.g. 2023-10-25T14:00:00Z or 2023-10-25T14:00:00+00:00)
                clean_time = new_start_time_input.replace('Z', '+00:00')
                dt = datetime.fromisoformat(clean_time)
                if timezone.is_naive(dt):
                    new_start_time = timezone.make_aware(dt)
                else:
                    new_start_time = dt
            except ValueError:
                # Fallback to legacy formats
                try:
                    if 'T' in new_start_time_input:
                        dt = datetime.strptime(new_start_time_input, '%Y-%m-%dT%H:%M')
                    else:
                        dt = datetime.strptime(new_start_time_input, '%Y-%m-%d %H:%M')
                    new_start_time = timezone.make_aware(dt)
                except ValueError:
                    raise ValidationError("Invalid date format.")
        else:
            new_start_time = new_start_time_input

        # 2. Basic Validation
        now = timezone.now()
        if new_start_time < now:
            raise ValidationError("Cannot reschedule to a time in the past.")
        
        # 3. Handle Coach Change
        target_coach = booking.coach
        if new_coach_id and int(new_coach_id) != booking.coach.id:
            # Validate if user is allowed to switch to this coach
            if booking.enrollment and not booking.enrollment.coach:
                # If enrollment is open (no specific coach assigned), check if new coach is in offering
                if booking.enrollment.offering.coaches.filter(id=new_coach_id).exists():
                    target_coach = get_object_or_404(CoachProfile, id=new_coach_id)
                else:
                    raise ValidationError("Invalid coach selection.")
            else:
                raise ValidationError("Cannot change coach for this booking.")

        # 4. Availability Check
        if booking.enrollment:
            session_length = booking.enrollment.offering.session_length_minutes
        else:
            session_length = booking.get_duration_minutes() or 60

        available_slots = BookingService.get_slots_for_coach(
            target_coach, new_start_time.date(), session_length
        )
        
        is_available = False
        for slot in available_slots:
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            if slot_aware == new_start_time:
                is_available = True
                break
        
        if not is_available:
            raise ValidationError("That time slot is no longer available. Please choose another.")

        # 5. Double Booking Check (Race Condition)
        if SessionBooking.objects.filter(
            coach=target_coach,
            start_datetime=new_start_time,
            status__in=['BOOKED', 'PENDING_PAYMENT', 'RESCHEDULED']
        ).exclude(id=booking.id).exists():
            raise ValidationError("This time slot has already been booked. Please select another time.")

        # 6. Apply Changes
        if target_coach != booking.coach:
            booking.coach = target_coach
        
        result = booking.reschedule(new_start_time)
        
        if result == 'LATE':
            raise ValidationError("Sessions cannot be rescheduled within 24 hours of the start time.")
        elif result == 'ERROR':
            raise ValidationError("Cannot reschedule a canceled or completed session.")
            
        return booking

    @staticmethod
    def request_session_coverage(booking, requesting_coach, note=""):
        """
        Coach A (requesting_coach) asks for help covering a session.
        """
        if booking.coach != requesting_coach:
            raise ValidationError("Only the currently assigned coach can request coverage.")
            
        request = SessionCoverageRequest.objects.create(
            requesting_coach=requesting_coach,
            session=booking,
            note=note,
            status='PENDING'
        )
        return request

    @staticmethod
    @transaction.atomic
    def accept_session_coverage(coverage_request_id, accepting_coach):
        """
        Coach B (accepting_coach) accepts the request.
        """
        try:
            req = SessionCoverageRequest.objects.select_related('session').get(
                pk=coverage_request_id, 
                status='PENDING'
            )
        except SessionCoverageRequest.DoesNotExist:
            return False, "Request not found or already processed."

        # Validate: Prevent coach from accepting their own request
        if req.requesting_coach == accepting_coach:
            return False, "You cannot accept your own coverage request."

        # Check for Google Calendar conflicts (CoachBusySlot)
        if CoachBusySlot.objects.filter(
            coach=accepting_coach, 
            start_time__lt=req.session.end_datetime, 
            end_time__gt=req.session.start_datetime
        ).exists():
            return False, "You have a Google Calendar conflict at this time."

        # Execute Acceptance Logic
        success = req.accept(accepting_coach)
        
        if success:
            return True, f"You are now covering this session for {req.session.client.get_full_name()}."
        return False, "Could not accept request."

    @staticmethod
    def _create_1on1_booking(booking_data, user, start_datetime_obj, provider_coach=None):
        coach_id = booking_data.get('coach_id')
        enrollment_id = booking_data.get('enrollment_id')
        free_offer_id = booking_data.get('free_offer_id')
        
        enrollment = None
        free_offer = None
        session_length = 60 # Default
        price_in_cents = 0

        # 3. Validate Entitlement (Enrollment or Free Offer) & Infer Coach
        if enrollment_id:
            enrollment = get_object_or_404(
                ClientOfferingEnrollment.objects.select_for_update(), 
                id=enrollment_id, 
                client=user
            )
            if enrollment.remaining_sessions <= 0:
                raise ValidationError("No sessions remaining for this enrollment.")
            session_length = enrollment.offering.session_length_minutes
            
            # If explicit provider requested, use it; otherwise use enrollment primary
            if provider_coach:
                coach_id = provider_coach.id
            elif not coach_id and enrollment.coach:
                coach_id = enrollment.coach.id
            
        elif free_offer_id:
            free_offer = get_object_or_404(
                OneSessionFreeOffer.objects.select_for_update(),
                id=free_offer_id,
                client=user,
                status='APPROVED'
            )
            if free_offer.is_expired:
                raise ValidationError("This free offer has expired.")
            
            if not coach_id:
                coach_id = free_offer.coach.id
                
            if int(coach_id) != free_offer.coach.id:
                raise ValidationError("The selected coach does not match the approved free offer.")
        else:
            # If no enrollment/free offer, assume paid booking (if logic allows)
            # For now, sticking to existing logic which requires enrollment/offer
            # But if we wanted to support direct paid bookings, we'd set price here.
            raise ValidationError("Booking requires either an enrollment or a free offer.")

        if not coach_id:
            raise ValidationError("Coach ID is required for 1-on-1 bookings.")
        
        coach_profile = get_object_or_404(CoachProfile, id=coach_id)
        product_name = f"1-on-1 with {coach_profile.user.get_full_name()}"

        # 4. Availability Check
        available_slots = BookingService.get_slots_for_coach(coach_profile, start_datetime_obj.date(), session_length)
        
        is_available = False
        for slot in available_slots:
            slot_aware = slot if timezone.is_aware(slot) else timezone.make_aware(slot)
            if slot_aware == start_datetime_obj:
                is_available = True
                break
        
        if not is_available:
            raise ValidationError("That time slot is no longer available.")

        # Since 1-on-1s currently require enrollment/free offer, they are effectively "paid" or "free"
        # So we confirm immediately.
        status = 'BOOKED'

        # Calculate End Time Robustly (Handling DST)
        # Assuming coach_profile has a time_zone field, otherwise default to UTC
        coach_tz_str = getattr(coach_profile, 'time_zone', 'UTC')
        try:
            coach_tz = pytz.timezone(coach_tz_str)
        except pytz.UnknownTimeZoneError:
            coach_tz = pytz.UTC
            
        local_start = start_datetime_obj.astimezone(coach_tz)
        local_end = local_start + timedelta(minutes=session_length)
        local_end = coach_tz.normalize(local_end)
        end_datetime_obj = local_end.astimezone(pytz.UTC)

        # 5. Create Record
        booking = SessionBooking.objects.create(
            enrollment=enrollment, 
            offering=free_offer.offering if free_offer else None,
            coach=coach_profile,
            client=user,
            start_datetime=start_datetime_obj,
            end_datetime=end_datetime_obj,
            status=status
        )

        # 6. Post-Creation Logic (Free Offer Redemption)
        if free_offer:
            free_offer.session = booking
            free_offer.status = 'USED'
            free_offer.save()

        return {'type': 'confirmed', 'booking': booking}

    @staticmethod
    def send_confirmation_emails(request, booking, is_free_session=False):
        """
        Helper to send emails. 
        """
        try:
            dashboard_url = request.build_absolute_uri(reverse('accounts:account_profile'))
            
            # Client Email
            client_context = {
                'user': booking.client,
                'session': booking,
                'dashboard_url': dashboard_url,
                'is_free_session': is_free_session,
            }
            recipient = booking.client.email if booking.client else booking.guest_email
            
            send_transactional_email(
                recipient_email=recipient,
                subject="Your Coaching Session is Confirmed!",
                template_name='emails/booking_confirmation.html',
                context=client_context
            )

            # Coach Email
            if booking.coach:
                coach_context = {
                    'coach': booking.coach,
                    'client': booking.client or booking.guest_name,
                    'session': booking,
                    'is_free_session': is_free_session,
                }
                send_transactional_email(
                    recipient_email=booking.coach.user.email,
                    subject=f"New Session Booked",
                    template_name='emails/coach_notification.html',
                    context=coach_context
                )
        except Exception as e:
            logger.error(f"Failed to send confirmation emails for booking {booking.id}: {e}")