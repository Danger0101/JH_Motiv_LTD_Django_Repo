from django.db import models

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
    subject = models.CharField(max_length=200)
    content = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    recipient_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='SENT')

    def __str__(self):
        date_str = self.sent_at.strftime('%Y-%m-%d') if self.sent_at else "Draft"
        return f"{self.subject} ({date_str})"
