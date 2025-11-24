from django.db import models
from django.utils.text import slugify
from django.conf import settings

# Using string reference for the CustomUser model
# from accounts.models import CustomUser

REQUEST_STATUS_CHOICES = (
    ('PENDING', 'Pending'),
    ('APPROVED', 'Approved'),
    ('DENIED', 'Denied'),
)

class ContentPage(models.Model):
    """
    Stores static knowledge base content, studies, and downloadable workbooks.
    """
    title = models.CharField(max_length=200, verbose_name="Title")
    slug = models.SlugField(unique=True, max_length=255, help_text="A unique slug for clean URLs.")
    content = models.TextField(verbose_name="Content", help_text="Main body text, studies, coaching comparisons, etc.")
    is_published = models.BooleanField(default=False, verbose_name="Is Published")
    downloadable_file = models.FileField(
        upload_to='workbooks/',
        blank=True,
        null=True,
        verbose_name="Downloadable File",
        help_text="Optional mini workbook or other downloadable material."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Content Page"
        verbose_name_plural = "Content Pages"
        ordering = ['title']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)


class ExternalLink(models.Model):
    """
    A simple model for linking to external articles or studies.
    """
    content_page = models.ForeignKey(
        ContentPage,
        on_delete=models.CASCADE,
        related_name='external_links',
        verbose_name="Content Page"
    )
    title = models.CharField(max_length=200, verbose_name="Link Title")
    url = models.URLField(max_length=500, verbose_name="URL")

    class Meta:
        verbose_name = "External Link"
        verbose_name_plural = "External Links"

    def __str__(self):
        return self.title


class TasterSessionRequest(models.Model):
    """
    Manages client requests for the free 90-minute taster session.
    """
    client = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='taster_session_request',
        verbose_name="Client"
    )
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="Requested At")
    status = models.CharField(
        max_length=10,
        choices=REQUEST_STATUS_CHOICES,
        default='PENDING',
        verbose_name="Status"
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='approved_tasters',
        null=True,
        blank=True,
        verbose_name="Approver",
        help_text="The staff member who approved or denied the request."
    )
    decision_at = models.DateTimeField(null=True, blank=True, verbose_name="Decision At")
    notes = models.TextField(
        blank=True,
        verbose_name="Internal Notes",
        help_text="Notes for why the request was approved or denied."
    )

    class Meta:
        verbose_name = "Taster Session Request"
        verbose_name_plural = "Taster Session Requests"
        # The unique=True on the 'client' field already enforces the constraint.
        # If you needed a multi-column constraint, you would use:
        # unique_together = [('client',)]
        ordering = ['-requested_at']

    def __str__(self):
        return f"Taster request from {self.client.get_full_name()} - {self.status}"