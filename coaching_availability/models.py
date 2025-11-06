from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, date
from accounts.models import CoachProfile

# Choices for day of the week
DAY_CHOICES = (
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
)

class CoachAvailability(models.Model):
    """
    Defines a coach's recurring standard working hours for a specific day of the week.
    """
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='availabilities',
        verbose_name="Coach",
        help_text="The coach to whom this availability belongs."
    )
    day_of_week = models.IntegerField(
        choices=DAY_CHOICES,
        verbose_name="Day of the Week",
        help_text="The day of the week for this availability slot."
    )
    start_time = models.TimeField(
        verbose_name="Start Time",
        help_text="The start time of the availability slot."
    )
    end_time = models.TimeField(
        verbose_name="End Time",
        help_text="The end time of the availability slot."
    )

    class Meta:
        verbose_name = "Coach Availability"
        verbose_name_plural = "Coach Availabilities"
        unique_together = ('coach', 'day_of_week', 'start_time', 'end_time')
        ordering = ['coach', 'day_of_week', 'start_time']

    def __str__(self):
        return f"{self.coach.user.get_full_name()} - {self.get_day_of_week_display()}: {self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    @classmethod
    def get_available_time_ranges_for_day(cls, coach_id, day_int):
        """
        Returns a list of (start_time, end_time) tuples for a given coach and day.
        """
        availabilities = cls.objects.filter(coach_id=coach_id, day_of_week=day_int).order_by('start_time')
        return [(a.start_time, a.end_time) for a in availabilities]


class CoachVacation(models.Model):
    """
    Defines periods when a coach is completely unavailable due to vacation.
    """
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='vacations',
        verbose_name="Coach",
        help_text="The coach taking the vacation."
    )
    start_date = models.DateField(
        verbose_name="Start Date",
        help_text="The start date of the vacation period."
    )
    end_date = models.DateField(
        verbose_name="End Date",
        help_text="The end date of the vacation period."
    )
    cancel_bookings = models.BooleanField(
        default=True,
        verbose_name="Cancel Existing Bookings",
        help_text="If checked, all bookings within this vacation period will be automatically cancelled."
    )

    class Meta:
        verbose_name = "Coach Vacation"
        verbose_name_plural = "Coach Vacations"
        ordering = ['coach', 'start_date']

    def __str__(self):
        return f"{self.coach.user.get_full_name()} Vacation: {self.start_date} to {self.end_date}"

    def clean(self):
        """
        Ensures that the end_date is not before the start_date.
        """
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before the start date.")

    @classmethod
    def is_coach_on_vacation(cls, coach_id, check_date):
        """
        Checks if a coach is on vacation on a specific date.
        Returns True if the date falls within any vacation period for the coach.
        """
        return cls.objects.filter(
            coach_id=coach_id,
            start_date__lte=check_date,
            end_date__gte=check_date
        ).exists()