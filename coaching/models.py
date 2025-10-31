from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError 


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
        return f"{self.coach.username}: {day} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


class CoachOffering(models.Model):
    """Defines a specific service offered by a coach, now supporting both direct pricing and a new token-based system."""
    BOOKING_TYPE_CHOICES = [
        ('token', 'Token-based'),
        ('price', 'Direct Price'),
    ]
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='offerings',
        limit_choices_to={'is_coach': True}
    )
    name = models.CharField(max_length=255, help_text="Public-facing service name.")
    slug = models.SlugField(max_length=255, help_text="URL-friendly identifier.")
    description = models.TextField()
    duration_minutes = models.IntegerField(help_text="Duration in minutes (e.g., 60 or 90).")
    booking_type = models.CharField(
        max_length=10,
        choices=BOOKING_TYPE_CHOICES,
        default='token',
        help_text="Determines if this session is booked with tokens or a direct price."
    )
    price = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Required only if booking_type is 'Direct Price'."
    )
    tokens_required = models.PositiveIntegerField(
        default=1,
        help_text="Number of tokens required to book this session (if token-based)."
    )
    is_active = models.BooleanField(default=True, help_text="Controls visibility on the public site.")
    class Meta:
        verbose_name = "Coach Offering"
        verbose_name_plural = "Coach Offerings"
        unique_together = ('coach', 'slug') 

    def __str__(self):
        return f"{self.name} by {self.coach.username}"

    def clean(self):
        if self.booking_type == 'price' and self.price is None:
            raise ValidationError('Price is required for sessions with a direct price.')
        if self.booking_type == 'token' and self.price is not None:
            self.price = None # Ensure price is null for token-based offerings



class CoachingProgram(models.Model):
    """
    Represents a purchasable coaching program that grants tokens and access for a specific duration.
    e.g., '3-Month Bi-Weekly Coaching'.
    """
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.PositiveIntegerField(help_text="How many months of access this program grants.")
    tokens_granted = models.PositiveIntegerField(help_text="Number of session tokens granted upon purchase.")
    is_active = models.BooleanField(default=True, help_text="Whether this program is available for purchase.")

    def __str__(self):
        return self.name


class CoachProgramLink(models.Model):
    """Links a specific coach to a CoachingProgram they are authorized to teach."""
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_coach': True},
        related_name='program_links'
    )
    program = models.ForeignKey(
        CoachingProgram,
        on_delete=models.CASCADE,
        related_name='coach_links'
    )

    class Meta:
        unique_together = ('coach', 'program')
        verbose_name = "Coach Program Link"
    
    def __str__(self):
        return f"{self.coach.username} authorized for {self.program.name}"


class UserProgram(models.Model):
    """Links a user to a coaching program they have purchased.This tracks their access period."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='coaching_programs')
    program = models.ForeignKey(CoachingProgram, on_delete=models.PROTECT, related_name='user_enrollments')
    purchase_date = models.DateField(default=timezone.now)
    start_date = models.DateField()
    end_date = models.DateField(help_text="The last day the user can book sessions under this program.")

    class Meta:
        ordering = ['-end_date']

    def __str__(self):
        return f"{self.user.username} enrolled in {self.program.name}"

    def save(self, *args, **kwargs):
        if not self.pk:
            self.start_date = self.purchase_date
            self.end_date = self.start_date + timezone.timedelta(days=self.program.duration_months * 30) # Approximation
        super().save(*args, **kwargs)



class Token(models.Model):
    """Represents a single coaching session token."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tokens')
    
    # MODIFIED: Made null=True, blank=True to allow for free/taster tokens
    user_program = models.ForeignKey(
        'UserProgram', 
        on_delete=models.CASCADE, 
        related_name='tokens',
        null=True, # Allows tokens not tied to a purchase
        blank=True
    )
    
    # NEW: Flag to track if this is the one-time free token
    is_taster = models.BooleanField(default=False) 
    
    purchase_date = models.DateTimeField(auto_now_add=True)
    expiration_date = models.DateTimeField()
    session = models.OneToOneField(
        'CoachingSession', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='used_token'
    )

    def is_valid(self):
        """Checks if the token is unused and not expired."""
        return self.session is None and timezone.now() < self.expiration_date

    def __str__(self):
        status = 'Used' if self.session else 'Available'
        token_type = ' (Taster)' if self.is_taster else ''
        return f"Token for {self.user.username} ({status}){token_type} - Expires {self.expiration_date.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if not self.pk:
            # If it's a taster token, set a shorter default expiration (e.g., 30 days)
            if self.is_taster:
                self.expiration_date = self.purchase_date + timezone.timedelta(days=30)
            # If it's a purchased token, set the program's defined expiration (or a default)
            elif self.user_program and self.user_program.end_date:
                 # Calculate expiration based on the program's end date (or similar logic)
                 # For simplicity, we'll use the 365 days default, but a real app might use program end date
                 self.expiration_date = self.purchase_date + timezone.timedelta(days=365)
            else:
                 self.expiration_date = self.purchase_date + timezone.timedelta(days=365)
                 
        super().save(*args, **kwargs)


# Define constants for TokenApplication status choices
TASTER_STATUS_PENDING = 'P'
TASTER_STATUS_APPROVED = 'A'
TASTER_STATUS_DENIED = 'D'
TASTER_STATUS_CHOICES = [
    (TASTER_STATUS_PENDING, 'Pending Review'),
    (TASTER_STATUS_APPROVED, 'Approved - Token Granted'),
    (TASTER_STATUS_DENIED, 'Denied'),
]
TASTER_STATUS_PENDING = 'P'
TASTER_STATUS_APPROVED = 'A'
TASTER_STATUS_DENIED = 'D'
TASTER_STATUS_CHOICES = [
    (TASTER_STATUS_PENDING, 'Pending Review'),
    (TASTER_STATUS_APPROVED, 'Approved - Token Granted'),
    (TASTER_STATUS_DENIED, 'Denied'),
]


class TokenApplication(models.Model):
    """
    Tracks a user's application for a token, primarily used for the
    one-time 'Momentum Catalyst Session' (free taster).
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='token_applications'
    )
    
    # Flag to identify if this application is for the free Taster Session
    is_taster = models.BooleanField(default=False)
    
    # Application status and history
    status = models.CharField(
        max_length=1,
        choices=TASTER_STATUS_CHOICES,
        default=TASTER_STATUS_PENDING
    )
    
    # Coach approval/denial tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_applications',
        limit_choices_to={'is_coach': True}
    )
    denied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='denied_applications',
        limit_choices_to={'is_coach': True}
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)
    denied_at = models.DateTimeField(null=True, blank=True)
    
    # Coach's optional reason for denial
    denial_reason = models.TextField(blank=True)

    class Meta:
        verbose_name = "Token Application"
        verbose_name_plural = "Token Applications"
        # Unique constraint: A user can only have one PENDING or APPROVED taster application
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'is_taster'], 
                condition=models.Q(is_taster=True, status__in=[TASTER_STATUS_PENDING, TASTER_STATUS_APPROVED]),
                name='unique_pending_or_approved_taster'
            )
        ]
    
    def __str__(self):
        return f"Application by {self.user.username} - Status: {self.get_status_display()}"