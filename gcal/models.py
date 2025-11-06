from django.db import models
from django.utils import timezone
from accounts.models import CoachProfile

class GoogleCredentials(models.Model):
    """
    Stores the secure OAuth 2.0 tokens for a coach to interact with the Google Calendar API.
    """
    coach = models.OneToOneField(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='google_credentials',
        verbose_name="Coach"
    )
    calendar_id = models.CharField(
        max_length=255,
        verbose_name="Google Calendar ID",
        help_text="The ID of the specific calendar used for bookings (e.g., 'primary')."
    )
    access_token = models.TextField(
        verbose_name="Access Token",
        help_text="Short-lived token for authenticating API requests."
    )
    refresh_token = models.TextField(
        verbose_name="Refresh Token",
        help_text="Long-lived token to obtain a new access token without user interaction."
    )
    token_expiry = models.DateTimeField(
        verbose_name="Token Expiry",
        help_text="The exact UTC datetime when the access token expires."
    )
    token_created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Token Created At"
    )
    scopes = models.TextField(
        verbose_name="Granted Scopes",
        help_text="A space-delimited or JSON list of the permissions granted."
    )

    class Meta:
        verbose_name = "Google Credentials"
        verbose_name_plural = "Google Credentials"

    def __str__(self):
        return f"Google Credentials for {self.coach.user.get_full_name()}"

    @property
    def is_expired(self):
        """
        Checks if the current access token has expired.
        Returns True if the token is expired, False otherwise.
        """
        return timezone.now() >= self.token_expiry

    def save(self, *args, **kwargs):
        if not self.id:
            self.token_created_at = timezone.now()
        super().save(*args, **kwargs)