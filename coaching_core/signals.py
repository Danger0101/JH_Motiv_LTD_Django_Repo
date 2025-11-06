from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.text import slugify

from .models import Offering

@receiver(post_save, sender=Offering)
def auto_generate_offering_slug_and_set_status(sender, instance, created, **kwargs):
    """
    Handles two post-save operations for an Offering:
    1. Generates a unique slug when an offering is first created.
    2. Updates the active_status based on whether coaches are assigned.
    """
    # Use a flag to determine if a re-save is needed to avoid recursion
    needs_resave = False
    update_fields = []

    # 1. Slug Generation on creation
    if created and not instance.slug:
        new_slug = slugify(instance.name)
        # Ensure slug is unique
        counter = 1
        while Offering.objects.filter(slug=new_slug).exclude(pk=instance.pk).exists():
            new_slug = f"{slugify(instance.name)}-{counter}"
            counter += 1
        instance.slug = new_slug
        needs_resave = True
        update_fields.append('slug')

    # 2. Active Status Check
    # This assumes a ManyToManyField named 'coaches' exists on the Offering model.
    # If the logic is different, this part needs to be adjusted.
    if hasattr(instance, 'coaches'):
        has_coaches = instance.coaches.exists()
        if instance.active_status != has_coaches:
            instance.active_status = has_coaches
            needs_resave = True
            if 'active_status' not in update_fields:
                update_fields.append('active_status')

    # CRITICAL: Only re-save if something has changed, and only update specific fields
    # to prevent an infinite save loop.
    if needs_resave:
        # Using update_fields is the safest way to save in a post_save signal
        instance.save(update_fields=update_fields)
