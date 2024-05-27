from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from spellbook.models import Job
from spellbook.variants.variants_generator import generate_variants
from ..abstract_command import AbstractCommand


class Command(AbstractCommand):
    name = 'generate_variants'
    help = 'Generates variants based on combos, features, cards'

    def run(self, *args, **options):
        added, restored, removed = generate_variants(self.job, log_count=500 if 'PyPy' in self.interpreter else 300)
        if added == 0 and removed == 0 and restored == 0:
            message = 'Variants are already synced with'
        else:
            message = f'Generated {added} new variants, restored {restored} variants, removed {removed} variants for'
        message += ' all combos'
        self.stdout.write(self.style.SUCCESS(message))
        if self.job is not None and self.job.started_by is not None:
            LogEntry(
                user=self.job.started_by,
                content_type=ContentType.objects.get_for_model(Job),
                object_id=self.job.id,
                object_repr='Generated Variants',
                action_flag=ADDITION,
            ).save()
