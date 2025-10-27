from django.db import models
from django.conf import settings
from django.utils import timezone

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

class CoachCalendarCredentials(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'is_coach': True}
    )
    calendar_id = models.CharField(max_length=255)
    token_data = models.JSONField()

    def __str__(self):
        return f"Calendar credentials for {self.user}"