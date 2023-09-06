import traceback
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from spellbook.models import Job, Variant
from spellbook.variants.variants_generator import generate_variants


class Command(BaseCommand):
    help = 'Generates variants based on combos, features, cards'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )

    def handle(self, *args, **options):
        job = Job.get_or_start('generate_variants', options['job_id'])        
        if job is None and options['job_id'] is not None:
            raise CommandError('Job with id %s does not exist' % options['job_id'])
        elif job is None:
            raise CommandError('Job with name generate_variants already running')
        try:
            added, restored, removed = generate_variants(job)
            if added == 0 and removed == 0 and restored == 0:
                message = 'Variants are already synced with'
            else:
                message = f'Generated {added} new variants, restored {restored} variants, removed {removed} variants for'
            message += ' all combos'
            self.stdout.write(self.style.SUCCESS(message))

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
