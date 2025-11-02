from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import CoachOffering

@receiver(m2m_changed, sender=CoachOffering.coaches.through)
def update_offering_status_on_coach_change(sender, instance, action, **kwargs):
    """
    Signal to automatically update the is_active status of a CoachOffering
    based on whether it has any associated coaches.
    """
    if action in ["post_add", "post_remove", "post_clear"]:
        # After adding, removing, or clearing coaches, check the count.
        if instance.coaches.count() == 0:
            # If no coaches are left, deactivate the offering.
            if instance.is_active:
                instance.is_active = False
                instance.save(update_fields=['is_active'])
        else:
            # If there is at least one coach, ensure it's active.
            if not instance.is_active:
                instance.is_active = True
                instance.save(update_fields=['is_active'])