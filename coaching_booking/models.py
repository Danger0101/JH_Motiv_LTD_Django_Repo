from django.db import models
from django.utils import timezone
from datetime import timedelta
from accounts.models import User
from coaching_core.models import CoachProfile, Offering

SESSION_STATUS_CHOICES = (
    ('BOOKED', 'Booked'),
    ('COMPLETED', 'Completed'),
    ('CANCELED', 'Canceled'),
    ('RESCHEDULED', 'Rescheduled'),
)

from dateutil.relativedelta import relativedelta

class ClientOfferingEnrollment(models.Model):
    """
    Represents a client's enrollment in a specific coaching offering, tracking their sessions.
    """
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='enrollments',
        verbose_name="Client"
    )
    offering = models.ForeignKey(
        Offering,
        on_delete=models.PROTECT, # Don't delete enrollment if offering is deleted
        related_name='enrollments',
        verbose_name="Offering"
    )
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_enrollments',
        verbose_name="Assigned Coach"
    )
    total_sessions = models.IntegerField(
        verbose_name="Total Sessions",
        help_text="Initial number of sessions purchased."
    )
    remaining_sessions = models.IntegerField(
        verbose_name="Remaining Sessions",
        help_text="Number of sessions left for the client to book."
    )
    start_date = models.DateField(
        verbose_name="Start Date",
        null=True, blank=True,
        help_text="The date of the client's first booked session."
    )
    end_date = models.DateField(
        verbose_name="End Date",
        null=True, blank=True,
        help_text="The calculated end date of the package based on the offering terms."
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Is Active",
        help_text="True if the enrollment is current and has sessions remaining."
    )
    enrolled_on = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Enrolled On"
    )

    class Meta:
        verbose_name = "Client Offering Enrollment"
        verbose_name_plural = "Client Offering Enrollments"
        ordering = ['-enrolled_on']

    def __str__(self):
        return f"{self.client.get_full_name()} - {self.offering.name}"

    def save(self, *args, **kwargs):
        if not self.pk:  # If creating a new enrollment
            self.total_sessions = self.offering.total_number_of_sessions
            self.remaining_sessions = self.offering.total_number_of_sessions
            self.end_date = self.enrolled_on.date() + relativedelta(months=+5)
        super().save(*args, **kwargs)

    def add_session(self):
        """Increments the remaining sessions by one."""
        self.remaining_sessions += 1
        self.save()

    @property
    def is_complete(self):
        """Returns True if all sessions have been used."""
        return self.remaining_sessions <= 0

    @property
    def is_expired(self):
        """Returns True if the enrollment has passed its end date."""
        return timezone.now().date() > self.end_date


class SessionBooking(models.Model):
    """
    Represents a single scheduled session between a coach and a client.
    """
    enrollment = models.ForeignKey(
        ClientOfferingEnrollment,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="Enrollment",
        null=True, blank=True # Can be null for taster sessions
    )
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="Coach"
    )
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings',
        verbose_name="Client"
    )
    start_datetime = models.DateTimeField(
        verbose_name="Start Time"
    )
    end_datetime = models.DateTimeField(
        verbose_name="End Time"
    )
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS_CHOICES,
        default='BOOKED',
        verbose_name="Status"
    )
    gcal_event_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Google Calendar Event ID",
        help_text="The unique ID for the event in Google Calendar."
    )

    class Meta:
        verbose_name = "Session Booking"
        verbose_name_plural = "Session Bookings"
        unique_together = ('coach', 'start_datetime')
        ordering = ['start_datetime']

TASTER_SESSION_STATUS_CHOICES = (
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('REJECTED', 'Rejected'),
    ('BOOKED', 'Booked'),
)

class TasterSession(models.Model):
    """
    Represents a request for a free taster session.
    """
    client = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='taster_sessions'
    )
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='taster_sessions'
    )
    status = models.CharField(
        max_length=20,
        choices=TASTER_SESSION_STATUS_CHOICES,
        default='PENDING'
    )
    requested_on = models.DateTimeField(auto_now_add=True)
    approved_on = models.DateTimeField(null=True, blank=True)
    booking_expiry_date = models.DateField(null=True, blank=True)
    session_booking = models.OneToOneField(
        SessionBooking,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='taster_session'
    )

    def approve(self):
        """Approves the taster session request."""
        self.status = 'APPROVED'
        self.approved_on = timezone.now()
        self.booking_expiry_date = self.approved_on.date() + relativedelta(months=+12)
        self.save()

    def reject(self):
        """Rejects the taster session request."""
        self.status = 'REJECTED'
        self.save()

    @property
    def is_expired(self):
        """Returns True if the booking window has expired."""
        if not self.booking_expiry_date:
            return False
        return timezone.now().date() > self.booking_expiry_date

    def __str__(self):
        return f"Session for {self.client.get_full_name()} with {self.coach.user.get_full_name()} at {self.start_datetime.strftime('%Y-%m-%d %H:%M')}"

    def get_duration_minutes(self):
        """Calculates the duration of the session in minutes."""
        if self.start_datetime and self.end_datetime:
            duration = self.end_datetime - self.start_datetime
            return int(duration.total_seconds() / 60)
        return 0

    def save(self, *args, **kwargs):
        # Automatically set client and coach from enrollment if not provided
        if self.enrollment and not self.client_id:
            self.client = self.enrollment.client
        if self.enrollment and not self.coach_id:
            self.coach = self.enrollment.coach
        
        # Automatically calculate end_datetime if not provided
        if self.start_datetime and not self.end_datetime:
            if self.enrollment:
                session_minutes = self.enrollment.offering.session_length_minutes
                self.end_datetime = self.start_datetime + timedelta(minutes=session_minutes)
            elif hasattr(self, 'taster_session') and self.taster_session:
                self.end_datetime = self.start_datetime + timedelta(minutes=90)

        if not self.pk and self.enrollment: # If new booking with enrollment, decrement remaining sessions
            self.enrollment.remaining_sessions -= 1
            self.enrollment.save()
            
        super().save(*args, **kwargs)

    def cancel(self):
        """Cancels the session and handles session forfeiture."""
        if self.enrollment:
            cancellation_cutoff = self.start_datetime - timedelta(hours=24)
            if timezone.now() >= cancellation_cutoff:
                # Late cancellation, session is forfeited
                self.status = 'CANCELED'
                self.save()
                return False # Indicates session was forfeited
            else:
                # Not a late cancellation, restore session
                self.enrollment.remaining_sessions += 1
                self.enrollment.save()
                self.status = 'CANCELED'
                self.save()
                return True # Indicates session was restored
        elif hasattr(self, 'taster_session') and self.taster_session:
            self.taster_session.status = 'APPROVED'
            self.taster_session.save()
            self.status = 'CANCELED'
            self.save()
            return True # Indicates taster session is available for re-booking

    def reschedule(self, new_start_time):
        """Reschedules the session and handles session forfeiture."""
        if self.enrollment:
            reschedule_cutoff = self.start_datetime - timedelta(hours=24)
            if timezone.now() >= reschedule_cutoff:
                # Late rescheduling, session is forfeited
                self.status = 'RESCHEDULED'
                self.save()
                return False # Indicates session was forfeited
            else:
                # Not a late rescheduling, update session time
                self.start_datetime = new_start_time
                session_minutes = self.enrollment.offering.session_length_minutes
                self.end_datetime = new_start_time + timedelta(minutes=session_minutes)
                self.status = 'RESCHEDULED'
                self.save()
                return True # Indicates session was successfully rescheduled
        elif hasattr(self, 'taster_session') and self.taster_session:
            self.start_datetime = new_start_time
            self.end_datetime = new_start_time + timedelta(minutes=90)
            self.status = 'RESCHEDULED'
            self.save()
            return True # Indicates taster session was successfully rescheduled