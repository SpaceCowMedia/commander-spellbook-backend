from django.core.management.base import BaseCommand
from ...models import WebsiteProperty, PROPERTY_KEYS


class Command(BaseCommand):
    help = 'Seed website properties'

    def handle(self, *args, **options):
        self.stdout.write('Seeding website properties...')
        properties = set(PROPERTY_KEYS)
        existing = set(WebsiteProperty.objects.values_list('key', flat=True))
        missing = properties - existing
        obsolete = existing - properties
        if missing:
            self.stdout.write(f'Creating missing properties: {", ".join(missing)}')
            WebsiteProperty.objects.bulk_create([
                WebsiteProperty(key=key)
                for key in missing
            ])
        if obsolete:
            self.stdout.write(f'Deleting obsolete properties: {", ".join(obsolete)}')
            WebsiteProperty.objects.filter(key__in=obsolete).delete()
        self.stdout.write(self.style.SUCCESS('Website properties were seeded.'))
