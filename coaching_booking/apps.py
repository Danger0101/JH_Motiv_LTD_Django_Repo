from django.apps import AppConfig


class CoachingBookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coaching_booking'

    def ready(self):
        """Import signal handlers when the app is ready."""
        import coaching_booking.signals

