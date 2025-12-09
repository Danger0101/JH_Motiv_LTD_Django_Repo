from django.db import models
from django.conf import settings
from accounts.fields import CustomEncryptedJSONField
from django.utils.text import slugify

class Dreamer(models.Model):
    # Basic fields for a newsletter subscriber/community member
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class DreamerProfile(models.Model):
    """Represents an individual or entity on the Wall of Dreamers."""
    
    # Core Data
    name = models.CharField(max_length=150, help_text="Full Name or Business Name (e.g., Ashley Johnson | Haijahr)")
    slug = models.SlugField(max_length=150, unique=True, blank=True, help_text="Unique URL-friendly identifier. Auto-generated from name if left blank.")
    story_excerpt = models.TextField(blank=True, help_text="A short paragraph about their journey or dream.")
    
    # Display Control
    is_featured = models.BooleanField(default=False, help_text="Check to feature this dreamer prominently.")
    order = models.PositiveIntegerField(default=0, help_text="Manual ordering for display on the site.")

    # NEW: Link to the User for login/dashboard access
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='dreamer_profile',
        help_text="Link this profile to a user account to enable the Affiliate Dashboard."
    )

    # Secure Payment Info
    payout_details = CustomEncryptedJSONField(
        blank=True, null=True,
        help_text="Encrypted JSON: {'bank_name': '...', 'sort_code': '...', 'account_number': '...'}"
    )

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Dreamer Profile"
        verbose_name_plural = "Dreamer Profiles"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        # Ensure slug is unique before saving
        # (A more robust solution might handle collisions with a counter)
        super().save(*args, **kwargs)

class ChannelLink(models.Model):
    """
    Represents a social media or website link for a dreamer.
    
    NOTE: The 'unique_together' constraint was removed to allow Dreamers to have 
    multiple links of the same type (e.g., two TikTok accounts).
    """
    CHANNEL_CHOICES = (
        ('website', 'Website/Personal Link'), 
        ('tiktok', 'TikTok'),
        ('instagram', 'Instagram'),
        ('youtube', 'YouTube'),
        ('spotify', 'Spotify'),
        ('facebook', 'Facebook'),
        ('linkedin', 'LinkedIn'),
        ('pinterest', 'Pinterest'),
        ('twitter', 'X (Twitter)'),
        ('github', 'GitHub'),
        ('etsy', 'Etsy'),
        ('email', 'Email Address (Mailto)'),
    )
    
    dreamer = models.ForeignKey(
        DreamerProfile, 
        related_name='channels', 
        on_delete=models.CASCADE,
        help_text="The Dreamer this link belongs to."
    )
    channel_type = models.CharField(
        max_length=50, 
        choices=CHANNEL_CHOICES, 
        help_text="Type of social media or link."
    )
    url = models.URLField(
        max_length=300, 
        help_text="Full URL to their profile or website (or mailto: link)."
    )

    class Meta:
        ordering = ['dreamer', 'channel_type'] # Order links logically within the admin
        verbose_name = "Channel Link"
        verbose_name_plural = "Channel Links"
        # unique_together constraint removed here.

    def __str__(self):
        # Uses get_channel_type_display() to show the user-friendly name (e.g., "YouTube")
        return f"{self.dreamer.name} - {self.get_channel_type_display()} Link"