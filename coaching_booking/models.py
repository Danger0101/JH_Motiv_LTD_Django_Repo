from django.db import models
from django.db.models import Q, UniqueConstraint, F
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from coaching_core.models import CoachProfile, Offering, Workshop
from dateutil.relativedelta import relativedelta
from django.core.exceptions import ValidationError

SESSION_STATUS_CHOICES = (
    ('PENDING_PAYMENT', 'Awaiting Payment'),
    ('BOOKED', 'Booked'),
    ('COMPLETED', 'Completed'),
    ('CANCELED', 'Canceled'),
    ('RESCHEDULED', 'Rescheduled'),
)

class ClientOfferingEnrollment(models.Model):
    """
    Connects a Client to an Offering and a specific 'Primary Coach'.
    The Primary Coach is the relationship owner, but individual sessions
    can be covered by others.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', verbose_name="Client")
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT, related_name='enrollments', verbose_name="Offering")
    
    # Renamed/Clarified: This is the coach the user chose at checkout.
    coach = models.ForeignKey(
        CoachProfile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=False, # Make mandatory in forms
        related_name='primary_client_enrollments', 
        verbose_name="Primary Coach"
    )
    
    total_sessions = models.IntegerField(verbose_name="Total Sessions")
    remaining_sessions = models.IntegerField(verbose_name="Remaining Sessions")
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name="Purchase Date")
    expiration_date = models.DateTimeField(null=True, blank=True, verbose_name="Expiration Date")
    is_active = models.BooleanField(default=True, verbose_name="Is Active")
    deactivated_on = models.DateTimeField(null=True, blank=True, verbose_name="Deactivated On")
    enrolled_on = models.DateTimeField(auto_now_add=True, verbose_name="Enrolled On")

    class Meta:
        verbose_name = "Client Offering Enrollment"
        verbose_name_plural = "Client Offering Enrollments"
        ordering = ['-enrolled_on']

    def __str__(self):
        return f"{self.client.get_full_name()} - {self.offering.name}"

    def save(self, *args, **kwargs):
        # Initialize total/remaining sessions on creation
        if not self.pk:
            self.total_sessions = self.offering.total_number_of_sessions
            self.remaining_sessions = self.offering.total_number_of_sessions

            # Fallback: If no coach selected (admin creation?), try to pick first available
            if not self.coach and self.offering:
                self.coach = self.offering.coaches.first()

        # Logic for managing is_active
        if self.remaining_sessions <= 0 and self.is_active:
            self.is_active = False
            if self.deactivated_on is None:
                self.deactivated_on = timezone.now()
        elif self.remaining_sessions > 0 and not self.is_active:
            self.is_active = True
            self.deactivated_on = None

        super().save(*args, **kwargs)

    def add_session(self):
        self.remaining_sessions += 1
        self.save()

    @property
    def is_complete(self):
        return self.remaining_sessions <= 0

    @property
    def is_expired(self):
        if self.expiration_date:
            return timezone.now() > self.expiration_date
        return False


class SessionBooking(models.Model):
    enrollment = models.ForeignKey(ClientOfferingEnrollment, on_delete=models.CASCADE, related_name='bookings', verbose_name="Enrollment", null=True, blank=True)
    # Decoupled Booking Fields
    offering = models.ForeignKey(Offering, on_delete=models.SET_NULL, null=True, blank=True, related_name='taster_bookings', help_text="Used for one-off bookings like taster sessions.")
    workshop = models.ForeignKey(Workshop, on_delete=models.SET_NULL, related_name='bookings', verbose_name="Workshop", null=True, blank=True)
    
    # The Coach actually delivering the session (can differ from enrollment.coach)
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='delivered_bookings', verbose_name="Session Provider", null=True, blank=True)
    
    # User / Guest Fields
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Client", null=True, blank=True)
    guest_email = models.EmailField(blank=True, verbose_name="Guest Email")
    guest_name = models.CharField(max_length=255, blank=True, verbose_name="Guest Name")
    
    start_datetime = models.DateTimeField(verbose_name="Start Time", db_index=True)
    end_datetime = models.DateTimeField(verbose_name="End Time")
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='BOOKED', verbose_name="Status")
    
    # Coverage Tracking
    is_coverage_session = models.BooleanField(default=False, help_text="True if this session is being covered by a coach other than the primary enrollment coach.")
    
    # Integrations & Meta
    gcal_event_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Google Calendar Event ID")
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Payment Fields
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True, null=True)
    amount_paid = models.IntegerField(default=0) # In cents
    is_paid = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Session Booking"
        verbose_name_plural = "Session Bookings"
        ordering = ['start_datetime']
        constraints = [
            UniqueConstraint(
                fields=['coach', 'start_datetime'],
                condition=Q(status__in=['BOOKED', 'PENDING_PAYMENT', 'COMPLETED', 'RESCHEDULED']),
                name='unique_active_coach_slot'
            )
        ]

    def clean(self):
        # Validate that the delivering coach is not double-booked
        if self.start_datetime and self.end_datetime and self.coach and not self.workshop:
            query = SessionBooking.objects.filter(
                coach=self.coach,
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime,
            ).exclude(status='CANCELED')
            
            if self.pk:
                query = query.exclude(pk=self.pk)

            if query.exists():
                raise ValidationError(f"Coach {self.coach.user.get_full_name()} is already booked for this time.")

    def __str__(self):
        return f"Session for {self.client.get_full_name()} with {self.coach.user.get_full_name()} at {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    def get_duration_minutes(self):
        if self.start_datetime and self.end_datetime:
            duration = self.end_datetime - self.start_datetime
            return int(duration.total_seconds() / 60)
        return 0

    @property
    def meeting_link(self):
        """
        Returns the meeting link. Checks the workshop first.
        """
        if self.workshop and self.workshop.meeting_link:
            return self.workshop.meeting_link
        return getattr(self, 'google_meet_link', None)

    def save(self, *args, **kwargs):
        # Set Client defaults
        if self.enrollment and not self.client_id and not self.guest_email:
            self.client = self.enrollment.client
            
        # Coach Assignment Logic
        if self.enrollment and not self.coach_id:
            # Default to the Primary Coach
            self.coach = self.enrollment.coach
        
        # Determine if this is a coverage session
        if self.enrollment and self.coach and self.enrollment.coach:
            if self.coach != self.enrollment.coach:
                self.is_coverage_session = True
            else:
                self.is_coverage_session = False

        # Set Durations
        if self.start_datetime and not self.end_datetime:
            if self.enrollment:
                session_minutes = self.enrollment.offering.session_length_minutes
                self.end_datetime = self.start_datetime + timedelta(minutes=session_minutes)
            else:
                self.end_datetime = self.start_datetime + timedelta(minutes=60)

        # Decrement sessions only on new booking
        if not self.pk and self.enrollment:
            self.enrollment.remaining_sessions -= 1
            self.enrollment.save()
            
        super().save(*args, **kwargs)
        
    @property
    def earnings_recipient(self):
        """Who receives the payout?"""
        return self.coach

    def cancel(self):
        """Standard cancellation logic (refunds credit if early)."""
        if self.status in ['CANCELED', 'COMPLETED']:
            return False

        now = timezone.now()
        cutoff = self.start_datetime - timedelta(hours=24)
        is_early = now < cutoff

        if is_early:
            if self.enrollment:
                self.enrollment.refresh_from_db()
                self.enrollment.remaining_sessions += 1
                self.enrollment.save()
            
            if hasattr(self, 'free_offer') and self.free_offer:
                self.free_offer.status = 'APPROVED'
                self.free_offer.session = None
                self.free_offer.save()

        self.status = 'CANCELED'
        self.save()
        return is_early

    @property
    def is_late_cancellation_window(self):
        """
        Returns True if the session is within 24 hours of starting (and hasn't started yet).
        """
        if self.status != 'BOOKED':
            return False
        now = timezone.now()
        cutoff = self.start_datetime - timedelta(hours=24)
        return cutoff <= now < self.start_datetime

    def reschedule(self, new_start_time):
        """
        Reschedules the session.
        Returns 'SUCCESS' or 'LATE' if within 24h.
        """
        if self.status in ['CANCELED', 'COMPLETED']:
            return 'ERROR'

        now = timezone.now()
        cutoff = self.start_datetime - timedelta(hours=24)

        if now >= cutoff:
            return 'LATE'

        current_duration = self.end_datetime - self.start_datetime

        self.start_datetime = new_start_time
        if self.enrollment:
            session_minutes = self.enrollment.offering.session_length_minutes
            self.end_datetime = new_start_time + timedelta(minutes=session_minutes)
        else:
            self.end_datetime = new_start_time + current_duration
            
        self.status = 'RESCHEDULED'
        self.save()
        return 'SUCCESS'


class SessionCoverageRequest(models.Model):
    """
    Mechanism for Coach A to request Coach B (or anyone) to cover a session.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    )

    requesting_coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='outgoing_coverage_requests')
    
    # Optional: If null, the request is open to the "pool" of qualified coaches
    target_coach = models.ForeignKey(CoachProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_coverage_requests')
    
    session = models.ForeignKey(SessionBooking, on_delete=models.CASCADE, related_name='coverage_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    note = models.TextField(blank=True, help_text="Notes for the covering coach.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Session Coverage Request"
        verbose_name_plural = "Session Coverage Requests"

    def accept(self, accepting_coach):
        """
        Logic to transfer the session to the accepting coach.
        """
        if self.status != 'PENDING':
            return False
            
        self.status = 'ACCEPTED'
        self.target_coach = accepting_coach # Ensure we record who accepted it
        self.save()
        
        # Update the actual session booking
        self.session.coach = accepting_coach
        self.session.is_coverage_session = True
        self.session.save()
        
        # Reject other pending requests for this session
        self.session.coverage_requests.exclude(pk=self.pk).update(status='REJECTED')
        
        return True

class OneSessionFreeOffer(models.Model):
    """
    Represents a single, non-paid, coach-approved coaching session offer
    with a one-month redemption deadline.
    """
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DECLINED', 'Declined'),
        ('USED', 'Used'),
    )
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='free_offers', verbose_name="Client")
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='approved_free_offers', verbose_name="Assigned Coach")
    offering = models.ForeignKey(Offering, on_delete=models.CASCADE, related_name='taster_offers', null=True, blank=True, help_text="The specific offering this taster is for.")
    date_offered = models.DateTimeField(default=timezone.now, verbose_name="Date Offered/Created")
    redemption_deadline = models.DateTimeField(null=True, blank=True, verbose_name="Redemption Deadline", help_text="The date by which the session must be booked AND scheduled.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    
    # Link to the resulting SessionBooking, which confirms the redemption
    session = models.OneToOneField('SessionBooking', on_delete=models.SET_NULL, null=True, blank=True, related_name='free_offer', verbose_name="Booked Session")

    class Meta:
        verbose_name = "One Session Free Offer"
        verbose_name_plural = "One Session Free Offers"
        ordering = ['-date_offered']
        
    def __str__(self):
        return f"Free Session for {self.client.get_full_name()} with {self.coach.user.get_full_name()} - Status: {self.get_status_display()}"

    def save(self, *args, **kwargs):
        # Calculate redemption_deadline on creation
        if not self.pk and not self.redemption_deadline:
            # Set the deadline for 1 calendar month from the offer date.
            self.redemption_deadline = self.date_offered + relativedelta(months=1)
            
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        """Checks if the offer has expired based on the deadline."""
        if self.redemption_deadline:
            return timezone.now() > self.redemption_deadline
        return False

class CoachBusySlot(models.Model):
    """
    A local cache of external calendar events (Google/Outlook).
    If a record exists here, the time is BLOCKED.
    """
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='busy_slots')
    external_id = models.CharField(max_length=255, unique=True) # Google Event ID
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    # Metadata for debugging
    source = models.CharField(max_length=50, default='GOOGLE_CALENDAR')
    last_synced = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['coach', 'start_time', 'end_time'])]
