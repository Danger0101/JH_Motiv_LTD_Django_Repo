from django.db import models
from django.conf import settings
from django.utils import timezone

# Create your models here.

class NewsletterSubscriber(models.Model):
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email

class NewsletterCampaign(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
    ]
    TEMPLATE_CHOICES = [
        ('standard', 'Standard (Text Focused)'),
        ('hero', 'Visual Impact (Big Image)'),
        ('showcase', 'Product Showcase (Grid)'),
    ]
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recipient_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SENT')
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='standard')

    def __str__(self):
        date_str = self.sent_at.strftime('%Y-%m-%d') if self.sent_at else "Draft"
        return f"{self.subject} ({date_str})"

class CheatUsage(models.Model):
    code_used = models.CharField(max_length=100)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    action_triggered = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.code_used} used by {self.user or 'Anonymous'} at {self.timestamp}"

class EmailResendLog(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resend to {self.email} at {self.timestamp}"

class Newsletter(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('sent', 'Sent'),
    ]
    
    TEMPLATE_CHOICES = [
        ('standard', 'Standard (Text Focused)'),
        ('hero', 'Visual Impact (Big Image)'),
        ('showcase', 'Product Showcase (Grid)'),
    ]

    subject = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, help_text="Auto-generated for the browser view version")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="Schedule for future sending")
    template = models.CharField(max_length=20, choices=TEMPLATE_CHOICES, default='standard')
    
    # Content Fields
    header_image = models.ImageField(upload_to='newsletters/', blank=True, null=True, help_text="Top banner image (Recommended for Hero/Showcase layouts)")
    body = models.TextField(help_text="Main content. HTML is supported.")
    
    # Call to Action (Button)
    cta_text = models.CharField(max_length=50, blank=True, verbose_name="Button Text", help_text="E.g. 'Shop the Collection'")
    cta_link = models.URLField(blank=True, verbose_name="Button Link")

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify
            self.slug = slugify(self.subject) + f"-{timezone.now().strftime('%Y%m%d')}"
        super().save(*args, **kwargs)
