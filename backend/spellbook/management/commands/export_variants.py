import json
import gzip
import traceback
from pathlib import Path
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from spellbook.models import Variant, Job
from spellbook.serializers import VariantSerializer


def prepare_variant(variant: Variant):
    return VariantSerializer(variant).data


class Command(BaseCommand):
    help = 'Exports variants to a JSON file'

    def add_arguments(self, parser):
        # Named (optional) arguments
        parser.add_argument(
            '--file',
            type=Path,
            dest='file',
            default=settings.STATIC_BULK_FOLDER / 'variants.json'
        )
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )
        parser.add_argument(
            '--s3',
            action='store_true',
            dest='s3',
        )

    def handle(self, *args, **options):
        job = None
        if options['job_id']:
            try:
                job = Job.objects.get(id=options['job_id'])
            except Job.DoesNotExist:
                raise CommandError('Job with id %s does not exist' % options['job_id'])
        try:
            self.stdout.write('Fetching variants from db...')
            result = {
                'timestamp': timezone.now().isoformat(),
                'variants': [prepare_variant(v) for v in Variant.objects.prefetch_related('uses', 'requires', 'produces', 'of', 'includes').filter(status=Variant.Status.OK)],
            }

            if options['file'] is not None:

                output: Path = options['file'].resolve()
                self.stdout.write(f'Exporting variants to {output}...')
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                    json.dump(result, f)
                    json.dump(result, fz)
                self.stdout.write('Done')

            if options['s3']:
                self.stdout.write('Uploading to S3...')
                from utils.s3_upload import upload_dictionary_aws
                upload_dictionary_aws(result, 'variants.json')
                self.stdout.write('Done')

            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.SUCCESS
                v = result['variants']
                job.message = f'Successfully exported {len(v)} variants'
                job.save()
                if job.started_by is not None:
                    LogEntry(
                        user=job.started_by,
                        content_type=ContentType.objects.get_for_model(Variant),
                        object_repr='Exported Variants',
                        action_flag=CHANGE
                    ).save()
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Failed to export variants: {e}'
            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.FAILURE
                job.message = message
                job.save()
