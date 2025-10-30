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
    # ... (rest of CoachingSession model remains the same)
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


# --- Existing Model: CoachVacationBlock ---
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


# =======================================================
# NEW MODEL: SpecificAvailability (One-Off Adjustments)
# =======================================================
class SpecificAvailability(models.Model):
    """
    Allows a coach to define specific available time ranges for a single, non-recurring date.
    """
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


# =======================================================
# NEW MODEL: RecurringAvailability (Weekly Schedule)
# =======================================================
class RecurringAvailability(models.Model):
    """
    Defines the coach's standard, repeatable working hours for each day of the week.
    """
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
        unique_together = ('coach', 'day_of_week', 'start_time', 'end_time')

    def __str__(self):
        day = self.get_day_of_week_display()
        status = "Available" if self.is_available else "Unavailable"
        return f"{self.coach.username}: {day} ({self.start_time.strftime('%I:%M %p')} - {self.end_time.strftime('%I:%M %p')})"


# =======================================================
# NEW MODEL: COACH OFFERING
# =======================================================
class CoachOffering(models.Model):
    """
    Defines a specific service or package offered by a coach (the final feature).
    """
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
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True, help_text="Controls visibility on the public site.")

    class Meta:
        verbose_name = "Coach Offering"
        verbose_name_plural = "Coach Offerings"
        unique_together = ('coach', 'slug') 

    def __str__(self):
        return f"{self.name} by {self.coach.username}"