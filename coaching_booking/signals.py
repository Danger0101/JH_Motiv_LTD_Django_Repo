from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import SessionBooking
from gcal.utils import create_calendar_event, update_calendar_event, delete_calendar_event


@receiver(post_save, sender=SessionBooking)
def handle_session_booking_save(sender, instance, created, **kwargs):
    """
    Handles the creation, update, and cancellation of Google Calendar events
    when a SessionBooking is saved.
    """
    if not instance.coach.google_credentials:
        return

    if created:
        # Create a new calendar event
        event = create_calendar_event(
            coach_profile=instance.coach,
            summary=f"Coaching Session with {instance.client.get_full_name()}",
            description=f"Coaching session for the offering: {instance.enrollment.offering.name if instance.enrollment else 'Taster Session'}",
            start_time=instance.start_datetime,
            end_time=instance.end_datetime,
            attendees=[
                {'email': instance.client.email},
                {'email': instance.coach.user.email}
            ]
        )
        if event:
            # We must use .update() here to avoid triggering the post_save signal again (recursion)
            SessionBooking.objects.filter(pk=instance.pk).update(gcal_event_id=event.get('id'))
    else:
        # Update or delete the calendar event
        if instance.gcal_event_id:
            if instance.status == 'CANCELED':
                delete_calendar_event(
                    coach_profile=instance.coach,
                    event_id=instance.gcal_event_id
                )
            else:
                updated_or_created_event = update_calendar_event(
                    coach_profile=instance.coach,
                    event_id=instance.gcal_event_id,
                    summary=f"Coaching Session with {instance.client.get_full_name()}",
                    description=f"Coaching session for the offering: {instance.enrollment.offering.name if instance.enrollment else 'Taster Session'}",
                    start_time=instance.start_datetime,
                    end_time=instance.end_datetime,
                    attendees=[
                        {'email': instance.client.email},
                        {'email': instance.coach.user.email}
                    ]
                )
                # If the event was recreated (new ID), update the DB without triggering signals
                if updated_or_created_event and updated_or_created_event.get('id') != instance.gcal_event_id:
                     SessionBooking.objects.filter(pk=instance.pk).update(gcal_event_id=updated_or_created_event.get('id'))

@receiver(post_delete, sender=SessionBooking)
def handle_session_booking_delete(sender, instance, **kwargs):
    """
    Handles the deletion of a Google Calendar event when a SessionBooking is deleted.
    """
    if instance.gcal_event_id and instance.coach.google_credentials:
        delete_calendar_event(
            coach_profile=instance.coach,
            event_id=instance.gcal_event_id
        )