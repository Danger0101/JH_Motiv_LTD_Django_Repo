from django.db import models
from django.db.models import Q, UniqueConstraint
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
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments', verbose_name="Client")
    offering = models.ForeignKey(Offering, on_delete=models.PROTECT, related_name='enrollments', verbose_name="Offering")
    coach = models.ForeignKey(CoachProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='client_enrollments', verbose_name="Assigned Coach")
    total_sessions = models.IntegerField(verbose_name="Total Sessions", help_text="Initial number of sessions purchased.")
    remaining_sessions = models.IntegerField(verbose_name="Remaining Sessions", help_text="Number of sessions left for the client to book.")
    purchase_date = models.DateTimeField(auto_now_add=True, verbose_name="Purchase Date")
    expiration_date = models.DateTimeField(null=True, blank=True, verbose_name="Expiration Date", help_text="The date when the enrollment expires.")
    is_active = models.BooleanField(default=True, verbose_name="Is Active", help_text="True if the enrollment is current and has sessions remaining.")
    deactivated_on = models.DateTimeField(null=True, blank=True, verbose_name="Deactivated On", help_text="The date and time when the enrollment became inactive (e.g., sessions ran out).")
    enrolled_on = models.DateTimeField(auto_now_add=True, verbose_name="Enrolled On")

    class Meta:
        verbose_name = "Client Offering Enrollment"
        verbose_name_plural = "Client Offering Enrollments"
        ordering = ['-enrolled_on']

    def __str__(self):
        return f"{self.client.get_full_name()} - {self.offering.name}"

    def save(self, *args, **kwargs):
        # Store original values if object already exists
        if self.pk:
            original_enrollment = ClientOfferingEnrollment.objects.get(pk=self.pk)
            # We only care if is_active changes, so we don't need all original fields
            original_is_active = original_enrollment.is_active
            # It's important to get the current state of remaining_sessions from the DB
            # before potentially modifying it.
            original_remaining_sessions = original_enrollment.remaining_sessions
        else:
            original_is_active = None
            original_remaining_sessions = None

        # Initialize total and remaining sessions on creation
        if not self.pk:
            self.total_sessions = self.offering.total_number_of_sessions
            self.remaining_sessions = self.offering.total_number_of_sessions

        # Logic for managing is_active and deactivated_on
        # Check if the enrollment is becoming inactive
        if self.remaining_sessions <= 0 and self.is_active:
            self.is_active = False
            if self.deactivated_on is None: # Only set if not already set
                self.deactivated_on = timezone.now()
        # Check if the enrollment is becoming active again (e.g., sessions added back)
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
    workshop = models.ForeignKey(Workshop, on_delete=models.CASCADE, related_name='bookings', verbose_name="Workshop", null=True, blank=True)
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='bookings', verbose_name="Coach", null=True, blank=True)
    
    # User / Guest Fields
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings', verbose_name="Client", null=True, blank=True)
    guest_email = models.EmailField(blank=True, verbose_name="Guest Email")
    guest_name = models.CharField(max_length=255, blank=True, verbose_name="Guest Name")
    
    start_datetime = models.DateTimeField(verbose_name="Start Time", db_index=True)
    end_datetime = models.DateTimeField(verbose_name="End Time")
    status = models.CharField(max_length=20, choices=SESSION_STATUS_CHOICES, default='BOOKED', verbose_name="Status")
    gcal_event_id = models.CharField(max_length=255, blank=True, null=True, verbose_name="Google Calendar Event ID", help_text="The unique ID for the event in Google Calendar.")
    reminder_sent = models.BooleanField(default=False, verbose_name="Reminder Sent", help_text="True if a reminder email has been sent for this session.")
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
        from django.core.exceptions import ValidationError
        if self.start_datetime and self.end_datetime and self.coach and not self.workshop:
            # Check for overlapping sessions for the same coach
            # Exclude self from query for updates
            query = SessionBooking.objects.filter(
                coach=self.coach,
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime,
            ).exclude(
                status='CANCELED'
            )
            if self.pk:
                query = query.exclude(pk=self.pk)

            if query.exists():
                raise ValidationError("This session overlaps with an existing active session for this coach.")

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
        if self.enrollment and not self.client_id and not self.guest_email:
            self.client = self.enrollment.client
        if self.enrollment and not self.coach_id:
            self.coach = self.enrollment.coach
        
        if self.start_datetime and not self.end_datetime:
            if self.enrollment:
                session_minutes = self.enrollment.offering.session_length_minutes
                self.end_datetime = self.start_datetime + timedelta(minutes=session_minutes)
            else:
                self.end_datetime = self.start_datetime + timedelta(minutes=60)

        # Decrement sessions only on creation if it's a new booking
        if not self.pk and self.enrollment:
            self.enrollment.remaining_sessions -= 1
            self.enrollment.save()
            
        super().save(*args, **kwargs)

    def cancel(self):
        """
        Cancels the session.
        Returns True if credit was restored (Early Cancel).
        Returns False if credit was forfeited (Late Cancel).
        """
        now = timezone.now()
        cutoff = self.start_datetime - timedelta(hours=24)

        if now < cutoff:
            # > 24 hours notice: Refund credit
            if self.enrollment:
                self.enrollment.remaining_sessions += 1
                self.enrollment.save()
            
            self.status = 'CANCELED'
            self.save()
            return True
        else:
            # < 24 hours notice: Forfeit credit
            self.status = 'CANCELED'
            self.save()
            return False

    def reschedule(self, new_start_time):
        """
        Reschedules the session.
        Returns 'SUCCESS' or 'LATE' if within 24h.
        """
        now = timezone.now()
        cutoff = self.start_datetime - timedelta(hours=24)

        if now >= cutoff:
            return 'LATE'

        self.start_datetime = new_start_time
        # end_datetime will be recalculated on save usually, but let's set it explicitly to be safe
        if self.enrollment:
            session_minutes = self.enrollment.offering.session_length_minutes
            self.end_datetime = new_start_time + timedelta(minutes=session_minutes)
        else:
            self.end_datetime = new_start_time + timedelta(minutes=60)
            
        self.status = 'RESCHEDULED'
        self.save()
        return 'SUCCESS'


class OneSessionFreeOffer(models.Model):
    """
    Represents a single, non-paid, coach-approved coaching session offer
    with a one-month redemption deadline.
    """
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='free_offers', verbose_name="Client")
    coach = models.ForeignKey(CoachProfile, on_delete=models.CASCADE, related_name='approved_free_offers', verbose_name="Assigned Coach")
    date_offered = models.DateTimeField(default=timezone.now, verbose_name="Date Offered/Created")
    redemption_deadline = models.DateTimeField(null=True, blank=True, verbose_name="Redemption Deadline", help_text="The date by which the session must be booked AND scheduled.")
    is_approved = models.BooleanField(default=False, verbose_name="Coach Approved", help_text="Must be approved by the coach before the client can book.")
    is_redeemed = models.BooleanField(default=False, verbose_name="Is Redeemed", help_text="Set to True once the session is successfully booked.")
    
    # Link to the resulting SessionBooking, which confirms the redemption
    session = models.OneToOneField('SessionBooking', on_delete=models.SET_NULL, null=True, blank=True, related_name='free_offer', verbose_name="Booked Session")

    class Meta:
        verbose_name = "One Session Free Offer"
        verbose_name_plural = "One Session Free Offers"
        ordering = ['-date_offered']
        
    def __str__(self):
        status = "Approved" if self.is_approved else "Pending Approval"
        return f"Free Session for {self.client.get_full_name()} with {self.coach.user.get_full_name()} - Status: {status}"

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
