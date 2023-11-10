import json
import gzip
import traceback
from pathlib import Path
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import transaction
from djangorestframework_camel_case.util import camelize
from spellbook.models import Variant, Job
from spellbook.serializers import VariantSerializer
from spellbook.views.variants import VariantViewSet
from ..s3_upload import upload_json_to_aws

DEFAULT_VARIANTS_FILE_NAME = 'variants.json'


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
            default=settings.STATIC_BULK_FOLDER / DEFAULT_VARIANTS_FILE_NAME
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
        job = Job.get_or_start('export_variants', options['job_id'])
        if job is None and options['job_id'] is not None:
            raise CommandError('Job with id %s does not exist' % options['job_id'])
        elif job is None:
            raise CommandError('Job with name export_variants already running')
        try:
            self.stdout.write('Fetching variants from db...')
            with transaction.atomic(durable=True):
                variants_source = VariantViewSet().get_queryset()
                result = {
                    'timestamp': timezone.now().isoformat(),
                    'variants': [prepare_variant(v) for v in variants_source],
                }

            camelized_json = camelize(result)
            if options['s3']:
                self.stdout.write('Uploading to S3...')
                upload_json_to_aws(camelized_json, DEFAULT_VARIANTS_FILE_NAME)
                self.stdout.write('Done')
            elif options['file'] is not None:
                output: Path = options['file'].resolve()
                self.stdout.write(f'Exporting variants to {output}...')
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                    json.dump(camelized_json, f)
                    json.dump(camelized_json, fz)
                self.stdout.write('Done')
            else:
                raise Exception('No file specified')

            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.message = 'Successfully exported %i variants' % len(result['variants'])
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
