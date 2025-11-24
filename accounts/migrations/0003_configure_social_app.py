# accounts/migrations/0003_configure_social_app.py

import os
from django.db import migrations
from django.core.exceptions import ImproperlyConfigured

def configure_social_app(apps, schema_editor):
    """
    Configures the Site and SocialApp for Google OAuth integration.
    """
    Site = apps.get_model('sites', 'Site')
    SocialApp = apps.get_model('socialaccount', 'SocialApp')

    # --- Update Site Information ---
    # The default site ID is 1, as set in settings.py
    site, created = Site.objects.get_or_create(pk=1)
    site.domain = 'jhmotiv-shop-ltd-official-040e4cbd5800.herokuapp.com'
    site.name = 'JH Motiv Shop'
    site.save()

    # --- Get Google Credentials from Environment ---
    client_id = os.getenv('GOOGLE_OAUTH2_CLIENT_ID')
    secret = os.getenv('GOOGLE_OAUTH2_CLIENT_SECRET')

    # Ensure credentials are set in the environment where `migrate` is run
    if not client_id or not secret:
        raise ImproperlyConfigured(
            "The GOOGLE_OAUTH2_CLIENT_ID and GOOGLE_OAUTH2_CLIENT_SECRET environment "
            "variables must be set before running this migration."
        )

    # --- Create or Update the Google SocialApp ---
    google_app, created = SocialApp.objects.update_or_create(
        provider='google',
        defaults={
            'name': 'Google Calendar Integration',
            'client_id': client_id,
            'secret': secret,
        }
    )

    # Link the SocialApp to the site
    google_app.sites.set([site])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_alter_user_managers_user_is_client_and_more'),
        # Add dependencies on the apps whose models are used in the migration
        ('sites', '0002_alter_domain_unique'), 
        ('socialaccount', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(configure_social_app),
    ]
