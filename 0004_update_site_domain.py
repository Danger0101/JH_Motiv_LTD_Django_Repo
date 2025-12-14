from django.db import migrations

def update_site_domain(apps, schema_editor):
    Site = apps.get_model('sites', 'Site')
    # Update the default site (ID 1) to the new domain
    # This ensures Google OAuth redirects match the registered callback
    site = Site.objects.get(pk=1)
    site.domain = 'jhmotiv.shop'
    site.name = 'JH Motiv Shop'
    site.save()

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_configure_social_app'),
    ]

    operations = [
        migrations.RunPython(update_site_domain),
    ]