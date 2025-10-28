# accounts/models.py (FIXED)

from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    is_coach = models.BooleanField(default=False)
    # RENAME: Renamed 'address' to 'billing_notes' to prevent the conflict.
    billing_notes = models.CharField(max_length=255, blank=True, null=True, 
                                     help_text="General notes or preferred billing address text.")

    def __str__(self):
        return self.username

class Address(models.Model):
    # FIX: Added related_name='addresses' to resolve the clash.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='addresses' 
    )
    full_name = models.CharField(max_length=255)
    street_address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    postcode = models.CharField(max_length=20)
    country = models.CharField(max_length=100)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.street_address}, {self.city}"

class MarketingPreference(models.Model):
    # This model remains correct as it already had a related_name
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='marketing_preference')
    is_subscribed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {'Subscribed' if self.is_subscribed else 'Unsubscribed'}"