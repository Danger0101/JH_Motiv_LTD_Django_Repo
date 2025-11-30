from django.db import models
from django.utils.text import slugify
from accounts.models import User, CoachProfile

# Choices for the duration type of the coaching offering
DURATION_TYPE_CHOICES = (
    ('WEEK', 'Week'),
    ('MONTH', 'Month'),
    ('PACKAGE', 'Package'),
)

class Offering(models.Model):
    """
    Defines the specific coaching package or service being sold.
    """
    name = models.CharField(
        max_length=255, 
        help_text="The Offering's Name/Title."
    )
    slug = models.SlugField(
        unique=True, 
        editable=False, 
        help_text="Unique slug for URL purposes, auto-generated from name."
    )
    description = models.TextField(
        help_text="Description of the offering."
    )
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        help_text="Cost of the package/service."
    )
    duration_type = models.CharField(
        max_length=10, 
        choices=DURATION_TYPE_CHOICES, 
        help_text="Duration measurement (e.g., Week, Month)."
    )
    total_length_units = models.IntegerField(
        help_text="e.g., 4 for 4 weeks or 3 for 3 months."
    )
    session_length_minutes = models.IntegerField(
        help_text="Length of each session in minutes (e.g., 60, 90)."
    )
    total_number_of_sessions = models.IntegerField(
        help_text="The initial session count for a client package."
    )
    is_whole_day = models.BooleanField(
        default=False,
        help_text="For offerings where times are set ad-hoc, bypassing fixed availability."
    )
    active_status = models.BooleanField(
        default=False,
        help_text="Is the offering currently active? Auto-set based on assigned coaches."
    )
    coaches = models.ManyToManyField(
        CoachProfile,
        related_name='offerings',
        blank=True,
        help_text="Coaches who can fulfill this offering."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='offerings_created'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='offerings_updated'
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Coaching Offering"
        verbose_name_plural = "Coaching Offerings"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Auto-update active_status based on whether coaches are assigned
        # The check `self.pk is not None` ensures this runs after the instance is first saved
        # and can have M2M relationships.
        if self.pk is not None:
            self.active_status = self.coaches.exists()
        else:
            # For a new instance, it can't have coaches yet.
            self.active_status = False

        super().save(*args, **kwargs)
        
        # If it's a new instance, the M2M can't be set until the object exists.
        # If we are creating it and adding coaches in the same operation,
        # we might need to re-evaluate active_status after the initial save.
        # A signal might be more robust here, but this is a common pattern.
        if self.pk and not self.active_status and self.coaches.exists():
            self.active_status = True
            super().save(update_fields=['active_status'])


    @property
    def display_length(self):
        """
        Returns a human-readable string for the offering's duration.
        e.g., "3 Months" or "8 Weeks"
        """
        if self.duration_type == 'PACKAGE':
            return "Package Deal"
        
        unit = self.get_duration_type_display()
        plural = 's' if self.total_length_units > 1 else ''
        return f"{self.total_length_units} {unit}{plural}"


class Workshop(models.Model):
    """
    Defines a group workshop event with a specific date, time, and capacity.
    """
    coach = models.ForeignKey(
        CoachProfile,
        on_delete=models.CASCADE,
        related_name='workshops',
        help_text="The coach hosting the workshop."
    )
    name = models.CharField(
        max_length=255,
        help_text="The Workshop's Name/Title."
    )
    slug = models.SlugField(
        unique=True,
        editable=False,
        help_text="Unique slug for URL purposes, auto-generated from name."
    )
    description = models.TextField(
        help_text="Detailed description of the workshop."
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Cost for attending the workshop."
    )
    date = models.DateField(
        help_text="The date of the workshop."
    )
    start_time = models.TimeField(
        help_text="The start time of the workshop."
    )
    end_time = models.TimeField(
        help_text="The end time of the workshop."
    )
    total_attendees = models.IntegerField(
        help_text="Maximum number of attendees allowed."
    )
    attendees = models.ManyToManyField(
        User,
        related_name='attended_workshops',
        blank=True,
        help_text="Users who have booked this workshop."
    )
    is_free = models.BooleanField(
        default=False,
        help_text="Is this a free workshop?"
    )
    active_status = models.BooleanField(
        default=True,
        help_text="Is the workshop currently active and bookable?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='workshops_created'
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='workshops_updated'
    )

    class Meta:
        ordering = ['date', 'start_time']
        verbose_name = "Workshop"
        verbose_name_plural = "Workshops"

    def __str__(self):
        return f"{self.name} on {self.date.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.name}-{self.date.strftime('%Y-%m-%d')}")
        super().save(*args, **kwargs)

    @property
    def remaining_spaces(self):
        """
        Calculates the number of remaining spaces for the workshop.
        """
        return self.total_attendees - self.attendees.count()

    @property
    def is_full(self):
        """
        Returns True if the workshop has no remaining spaces.
        """
        return self.remaining_spaces <= 0