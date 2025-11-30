from django.db import models
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator


class CoachAvailability(models.Model):
    """
    Represents a recurring weekly schedule for a coach.
    e.g., Every Monday 9-5.
    """
    DAYS_OF_WEEK = (
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    )
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    day_of_week = models.IntegerField(
        choices=DAYS_OF_WEEK,
        validators=[MinValueValidator(0), MaxValueValidator(6)]
    )  # 0=Monday, 6=Sunday
    start_time = models.TimeField()
    end_time = models.TimeField()



    def __str__(self):
        return f"{self.coach.username} - {self.get_day_of_week_display()} " \
               f"({self.start_time}-{self.end_time})"


class DateOverride(models.Model):
    """
    Represents a single date change to the recurring schedule.
    e.g., Next Friday is valid, or Next Friday I am working extra hours.
    """
    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='overrides'
    )
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ('coach', 'date')

    def __str__(self):
        return f"{self.coach.username} - {self.date} " \
               f"({'Available' if self.is_available else 'Unavailable'})"


class CoachVacation(models.Model):
    """
    Represents a block of time off for a coach.
    """

    BOOKING_HANDLING_CHOICES = (
        ('keep', 'Keep'),
        ('reschedule', 'Reschedule'),
        ('cancel', 'Cancel'),
    )

    coach = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='vacations'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    existing_booking_handling = models.CharField(
        max_length=10,
        choices=BOOKING_HANDLING_CHOICES,
        default='reschedule'
    )

    def __str__(self):
        return f"{self.coach.username} - Vacation: {self.start_date} to {self.end_date}"
