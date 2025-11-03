from django.core.management.base import BaseCommand
from coaching.models import CoachOffering
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Generates slugs for any existing CoachOfferings that are missing them.'

    def handle(self, *args, **options):
        offerings_without_slugs = CoachOffering.objects.filter(slug__in=['', None])
        updated_count = 0
        
        for offering in offerings_without_slugs:
            offering.slug = slugify(offering.name)
            offering.save()
            updated_count += 1
            
        if updated_count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully generated slugs for {updated_count} offerings.'))
        else:
            self.stdout.write(self.style.SUCCESS('All offerings already have slugs.'))
