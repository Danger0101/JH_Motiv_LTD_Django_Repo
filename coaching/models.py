from django.db import models
from django.conf import settings

class CoachingSession(models.Model):
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
    service_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.service_name} with {self.coach} at {self.start_time}"