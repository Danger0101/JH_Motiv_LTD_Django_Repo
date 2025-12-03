from django.db import models
from django.utils.text import slugify
from django.conf import settings

# Using string reference for the CustomUser model
# from accounts.models import CustomUser

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