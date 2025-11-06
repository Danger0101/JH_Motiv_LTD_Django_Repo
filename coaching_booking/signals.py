from django.db.models.signals import pre_save
from django.dispatch import receiver

from .models import ClientOfferingEnrollment

@receiver(pre_save, sender=ClientOfferingEnrollment)
def set_initial_session_counts(sender, instance, **kwargs):
    """
    Before a new ClientOfferingEnrollment is saved, this signal sets the initial
    session counts based on the purchased offering.
    """
    # Check if the instance is being created (it will not have a pk yet)
    if instance.pk is None:
        # The prompt assumes 'total_number_of_sessions', but the model has 'total_length_units'.
        # We will use the existing field.
        if instance.offering and hasattr(instance.offering, 'total_length_units'):
            session_count = instance.offering.total_length_units
            instance.total_sessions = session_count
            instance.remaining_sessions = session_count
            instance.is_active = True
