from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from .models import CoachOffering, UserOffering, SessionCredit, CreditApplication, CreditApplicationStatus

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


@receiver(post_save, sender=UserOffering)
def create_session_credits_for_offering(sender, instance, created, **kwargs):
    """
    When a UserOffering is first created, automatically create the
    corresponding number of SessionCredit objects.
    """
    if created:
        for _ in range(instance.offering.credits_granted):
            SessionCredit.objects.create(
                user=instance.user,
                user_offering=instance,
                is_taster=False
            )

@receiver(post_save, sender=CreditApplication)
def create_taster_credit_on_approval(sender, instance, created, **kwargs):
    """
    When a CreditApplication is approved, create the taster SessionCredit.
    """
    # Check if the status is now 'Approved' and if this is not the initial creation
    if not created and instance.status == CreditApplicationStatus.APPROVED:
        # Check if a credit has already been created for this application to avoid duplicates
        if not SessionCredit.objects.filter(user=instance.user, is_taster=True).exists():
            SessionCredit.objects.create(
                user=instance.user,
                is_taster=True
            )