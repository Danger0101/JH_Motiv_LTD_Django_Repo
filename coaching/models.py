from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class CoachingSession(models.Model):
    STATUS_CHOICES = [
        ('BOOKED', 'Booked'),
        ('PENDING', 'Pending'),
        ('CANCELLED', 'Cancelled'),
    ]

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coaching_sessions',
        limit_choices_to={'is_coach': True}
    )
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_sessions'
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(default=timezone.now)
    service_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    paid_out = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.service_name} with {self.coach} at {self.start_time}"



class CoachVacationBlock(models.Model):
    """Defines a date range where the coach is explicitly unavailable (e.g., vacation)."""
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vacation_blocks',
        limit_choices_to={'is_coach': True}
    )
    # ... (rest of CoachVacationBlock model remains the same)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=255, blank=True, null=True)
    override_allowed = models.BooleanField(default=False, help_text="If True, the coach can choose to book sessions during this block.")

    class Meta:
        verbose_name = "Vacation/Unbookable Block"
        verbose_name_plural = "Vacation/Unbookable Blocks"
        ordering = ['start_date']

    def __str__(self):
        return f"{self.coach.username} blocked from {self.start_date} to {self.end_date}"



class SpecificAvailability(models.Model):
    """Allows a coach to define specific available time ranges for a single, non-recurring date."""
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='specific_availability',
        limit_choices_to={'is_coach': True}
    )
    
    date = models.DateField(help_text="The specific day this availability applies to.")
    start_time = models.TimeField(help_text="Start time for this specific slot.")
    end_time = models.TimeField(help_text="End time for this specific slot.")
    is_available = models.BooleanField(
        default=True, 
        help_text="If True, this slot is available; if False, this slot is explicitly blocked (one-off block)."
    )

    class Meta:
        verbose_name = "Specific Availability Slot"
        verbose_name_plural = "Specific Availability Slots"
        unique_together = ('coach', 'date', 'start_time', 'end_time')
        ordering = ['date', 'start_time']

    def __str__(self):
        status = "Available" if self.is_available else "Blocked"
        return f"{self.coach.username}: {self.date} {status} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


class RecurringAvailability(models.Model):
    """Defines the coach's standard, repeatable working hours for each day of the week."""
    DAY_CHOICES = (
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'), (3, 'Thursday'),
        (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    )

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='recurring_availability',
        limit_choices_to={'is_coach': True}
    )
    
    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        help_text="Day of the week (0=Monday to 6=Sunday)."
    )
    
    start_time = models.TimeField(help_text="Start time for this day's availability.")
    end_time = models.TimeField(help_text="End time for this day's availability.")
    is_available = models.BooleanField(
        default=True, 
        help_text="If set to False, the coach is unavailable for the entire day."
    )

    class Meta:
        verbose_name = "Recurring Availability Block"
        verbose_name_plural = "Recurring Availability Blocks"
        ordering = ['day_of_week', 'start_time']
        unique_together = ('coach', 'day_of_week')

    def __str__(self):
        day = self.get_day_of_week_display()
        status = "Available" if self.is_available else "Unavailable"
        start_time_str = self.start_time.strftime('%I:%M %p') if self.start_time else '--:--'
        end_time_str = self.end_time.strftime('%I:%M %p') if self.end_time else '--:--'
        return f"{self.coach.username}: {day} ({start_time_str} - {end_time_str})"


class CoachOffering(models.Model):
    """Defines a specific, purchasable service offered by a coach."""
    coaches = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='offerings',
        limit_choices_to={'is_coach': True}
    )
    name = models.CharField(max_length=255, help_text="Public-facing service name.")
    slug = models.SlugField(max_length=255, help_text="URL-friendly identifier.")
    description = models.TextField()
    duration_minutes = models.IntegerField(help_text="Duration in minutes (e.g., 60 or 90).")
    price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        help_text="The price for this offering."
    )
    credits_granted = models.PositiveIntegerField(
        default=1,
        help_text="Number of session credits granted upon purchase."
    )
    duration_months = models.PositiveIntegerField(default=3, help_text="How many months of access this program grants.")
    is_active = models.BooleanField(default=True, help_text="Controls visibility on the public site.")
    rate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="The amount the coach will be paid for this offering.")

    class Meta:
        verbose_name = "Coach Offering"
        verbose_name_plural = "Coach Offerings"
        # unique_together = ('coach', 'slug') # Removed as coach is now ManyToMany

    def __str__(self):
        coach_names = ', '.join([coach.username for coach in self.coaches.all()])
        return f"{self.name} by {coach_names}"


class UserOffering(models.Model):
    """Links a user to a coaching offering they have purchased."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchased_offerings')
    offering = models.ForeignKey(CoachOffering, on_delete=models.PROTECT, related_name='user_enrollments')
    purchase_date = models.DateField(default=timezone.now)
    start_date = models.DateField()
    end_date = models.DateField(help_text="The last day the user can book sessions under this offering.")

    class Meta:
        ordering = ['-end_date']

    def __str__(self):
        return f"{self.user.username} enrolled in {self.offering.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.start_date = self.purchase_date
            self.end_date = self.start_date + relativedelta(months=self.offering.duration_months)
        super().save(*args, **kwargs)


class CoachPayout(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
    ]

    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payouts')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout of {self.amount} to {self.coach.username} - {self.status}"


class SessionCredit(models.Model):
    """Represents a single coaching session credit."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_credits')
    
    user_offering = models.ForeignKey(
        'UserOffering', 
        on_delete=models.CASCADE, 
        related_name='session_credits',
        null=True, 
        blank=True
    )
    
    is_taster = models.BooleanField(default=False) 
    
    purchase_date = models.DateTimeField(auto_now_add=True)
    expiration_date = models.DateTimeField()
    session = models.OneToOneField(
        'CoachingSession', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='used_credit'
    )

    def is_valid(self):
        """Checks if the credit is unused and not expired."""
        return self.session is None and timezone.now() < self.expiration_date

    def __str__(self):
        status = 'Used' if self.session else 'Available'
        credit_type = ' (Taster)' if self.is_taster else ''
        return f"Credit for {self.user.username} ({status}){credit_type} - Expires {self.expiration_date.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.purchase_date is None:
                self.purchase_date = timezone.now()
            if self.is_taster:
                self.expiration_date = self.purchase_date + timezone.timedelta(days=30)
            elif self.user_offering and self.user_offering.end_date:
                 self.expiration_date = self.purchase_date + timezone.timedelta(days=365)
            else:
                 self.expiration_date = self.purchase_date + timezone.timedelta(days=365)
                 
        super().save(*args, **kwargs)


# Define constants for CreditApplication status choices
CREDIT_APP_STATUS_PENDING = 'P'
CREDIT_APP_STATUS_APPROVED = 'A'
CREDIT_APP_STATUS_DENIED = 'D'
CREDIT_APP_STATUS_CHOICES = [
    (CREDIT_APP_STATUS_PENDING, 'Pending Review'),
    (CREDIT_APP_STATUS_APPROVED, 'Approved - Credit Granted'),
    (CREDIT_APP_STATUS_DENIED, 'Denied'),
]



class CreditApplication(models.Model):
    """
    Tracks a user's application for a credit, primarily used for the
    one-time 'Momentum Catalyst Session' (free taster).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='credit_applications'
    )
    
    is_taster = models.BooleanField(default=False)
    
    status = models.CharField(
        max_length=1,
        choices=CREDIT_APP_STATUS_CHOICES,
        default=CREDIT_APP_STATUS_PENDING
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_credit_applications',
        limit_choices_to={'is_coach': True}
    )
    denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='denied_credit_applications',
        limit_choices_to={'is_coach': True}
    )
    
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    denied_at = models.DateTimeField(null=True, blank=True)
    
    denial_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Credit Application"
        verbose_name_plural = "Credit Applications"
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_taster'], 
                condition=models.Q(is_taster=True, status__in=[CREDIT_APP_STATUS_PENDING, CREDIT_APP_STATUS_APPROVED]),
                name='unique_pending_or_approved_taster'
            )
        ]
    
    def __str__(self):
        return f"Application by {self.user.username} - Status: {self.get_status_display()}"


import uuid

class RescheduleRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
    ]

    session = models.OneToOneField(CoachingSession, on_delete=models.CASCADE, related_name='reschedule_request')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reschedule request for session {self.session.id} - {self.status}"


class CoachSwapRequest(models.Model):
    STATUS_CHOICES = [
        ('PENDING_COACH', 'Pending Coach Approval'),
        ('PENDING_USER', 'Pending User Approval'),
        ('ACCEPTED', 'Accepted'),
        ('DECLINED', 'Declined'),
    ]

    session = models.OneToOneField(CoachingSession, on_delete=models.CASCADE, related_name='swap_request')
    initiating_coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='initiated_swap_requests')
    receiving_coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_swap_requests')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_COACH')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Swap request for session {self.session.id} from {self.initiating_coach} to {self.receiving_coach} - {self.status}"


class CancellationPolicy(models.Model):
    USER_TYPE_CHOICES = [
        ('USER', 'User'),
        ('COACH', 'Coach'),
    ]

    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    hours_before_session = models.PositiveIntegerField()
    refund_percentage = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.user_type} cancellation policy: {self.refund_percentage}% refund if cancelled {self.hours_before_session} hours before." 


class SessionNote(models.Model):
    session = models.ForeignKey(CoachingSession, on_delete=models.CASCADE, related_name='notes')
    coach = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='session_notes')
    note = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note for session {self.session.id} by {self.coach.username}"


class Goal(models.Model):
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
    ]

    user_offering = models.ForeignKey(UserOffering, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
