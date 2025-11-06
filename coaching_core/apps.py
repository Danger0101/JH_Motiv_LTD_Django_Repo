from django.apps import AppConfig


class CoachingCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'coaching_core'

    def ready(self):
        """Import signal handlers when the app is ready."""
        import coaching_core.signals

