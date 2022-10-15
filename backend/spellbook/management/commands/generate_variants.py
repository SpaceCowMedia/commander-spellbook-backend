import traceback
from django.core.management.base import BaseCommand, CommandError
from spellbook.models import Combo
from spellbook.models import Job, Variant
from spellbook.variants import generate_variants, generate_variants_for_combo
from django.utils import timezone
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Generates variants based on combos, features, cards'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )
        parser.add_argument(
            '--combo',
            type=int,
            dest='combo_id',
            required=False,
        )

    def handle(self, *args, **options):
        job = None
        if options['job_id']:
            try:
                job = Job.objects.get(id=options['job_id'])
            except Job.DoesNotExist:
                raise CommandError('Job with id %s does not exist' % options['job_id'])
        try:
            if options['combo_id']:
                added, restored, removed = generate_variants_for_combo(Combo.objects.get(id=options['combo_id']), job)
            else:
                added, restored, removed = generate_variants(job)
            if added == 0 and removed == 0 and restored == 0:
                message = 'Variants are already synced with combos'
            else:
                message = f'Generated {added} new variants, restored {restored} variants, removed {removed} variants'
            self.stdout.write(self.style.SUCCESS(message))
            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.SUCCESS
                job.message = message
                job.save()
                if job.started_by is not None:
                    LogEntry(
                        user=job.started_by,
                        content_type=ContentType.objects.get_for_model(Variant),
                        object_repr='Generated Variants',
                        action_flag=CHANGE
                    ).save()
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Failed to generate variants: {e}'
            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.FAILURE
                job.message = message
                job.save()
