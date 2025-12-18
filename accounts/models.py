from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from .fields import CustomEncryptedJSONField
from timezone_field import TimeZoneField

class UserManager(BaseUserManager):
    """Custom manager for the User model."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)

    def get_coaches(self):
        """Returns a queryset of all users where is_coach=True."""
        return self.get_queryset().filter(is_coach=True)

    def get_clients(self):
        """Returns a queryset of all users where is_client=True."""
        return self.get_queryset().filter(is_client=True)

class User(AbstractUser):
    is_coach = models.BooleanField(
        default=False,
        help_text=_("Designates whether this user is a coaching staff member.")
    )
    is_client = models.BooleanField(
        default=True,
        help_text=_("Designates whether this user is a client.")
    )
    # Existing field - keeping this!
    billing_notes = models.CharField(max_length=255, blank=True, null=True,
                                     help_text="General notes or preferred billing address text.")
    business_name = models.CharField(max_length=255, blank=True, help_text="Company or Business Name for invoices/networking")
    
    # NEW FIELD: Stripe Customer ID
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True,
                                          help_text="The ID of this user in Stripe (e.g. cus_12345).")

    google_calendar_credentials = CustomEncryptedJSONField(max_length=4096, null=True, blank=True)
    
    is_on_vacation = models.BooleanField(default=False, help_text="If checked, the coach is immediately unbookable.")
    user_timezone = TimeZoneField(
        default='UTC', 
        help_text="User's preferred time zone for display and defining working hours."
    )

    objects = UserManager()

    def __str__(self):
        return self.username

class CoachProfile(models.Model):
    """
    Holds essential, non-security-related profile information for coaches.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='coach_profile',
        limit_choices_to={'is_coach': True}
    )
    bio = models.TextField(
        blank=True,
        help_text="A short bio describing the coach's style and background."
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Coach's contact phone number."
    )
    # For a production environment, consider using a library like django-timezone-field
    # and pytz to provide a list of valid time zones.
    time_zone = models.CharField(
        max_length=50,
        default='UTC',
        help_text="The coach's local time zone for accurate scheduling conversions."
    )
    public_photo = models.ImageField(
        upload_to='coach_photos/',
        blank=True,
        null=True,
        help_text="Optional public profile photo for the coach."
    )
    is_available_for_new_clients = models.BooleanField(
        default=True,
        help_text="Allows staff to quickly block new enrollments to this coach."
    )
    
    # Secure Payment Info
    payout_details = CustomEncryptedJSONField(
        blank=True, null=True,
        help_text="Encrypted JSON: {'bank_name': '...', 'sort_code': '...', 'account_number': '...'}"
    )
    last_synced = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of the last successful Google Calendar sync."
    )

    def __str__(self):
        return f"Profile for {self.user.get_full_name()}"


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
    subscribed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {'Subscribed' if self.is_subscribed else 'Unsubscribed'}"