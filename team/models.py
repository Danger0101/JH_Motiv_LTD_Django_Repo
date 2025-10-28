from django.db import models

class TeamMember(models.Model):
    """Stores data for an individual member of the JH Motiv team."""
    
    # Core Data
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=150, help_text="Job title or role (e.g., Founder & CEO, Lead Coach).")
    bio = models.TextField(help_text="A brief description or biography of the team member.")
    
    # Image & Display
    # NOTE: Requires 'Pillow' library installed: pip install Pillow
    profile_image = models.ImageField(
        upload_to='team_photos/', 
        help_text="Upload a professional photo for the team member."
    )
    is_active = models.BooleanField(default=True, help_text="Display on the Meet the Team page.")
    order = models.PositiveIntegerField(default=0, help_text="Manual ordering for display.")

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"

    def __str__(self):
        return f"{self.name} ({self.role})"