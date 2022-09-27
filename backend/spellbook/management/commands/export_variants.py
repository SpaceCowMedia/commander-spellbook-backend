import json
import gzip
from pathlib import Path
import traceback
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandError
from spellbook.models import Variant, Job
from spellbook.serializers import VariantSerializer
from django.conf import settings


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
            default=Path(settings.DEFAULT_BULK_FOLDER) / Path('variants.json')
        )
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )

    def handle(self, *args, **options):
        job = None
        if options['job_id']:
            try:
                job = Job.objects.get(id=options['job_id'])
            except Job.DoesNotExist:
                raise CommandError('Job with id %s does not exist' % options['job_id'])
        try:
            if options['file'] is None:
                raise Exception('No file specified')
            output: Path = options['file'].resolve()
            self.stdout.write('Fetching variants from db...')
            result = {
                'timestamp': timezone.now().isoformat(),
                'variants': [prepare_variant(v) for v in Variant.objects.filter(status=Variant.Status.OK)],
            }
            self.stdout.write(f'Exporting variants to {output}...')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                json.dump(result, f)
                json.dump(result, fz)
            self.stdout.write('Done')
            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.SUCCESS
                v = result['variants']
                job.message = f'Successfully exported {len(v)} variants'
                job.save()
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Failed to export variants: {e}'
            if job is not None:
                job.termination = timezone.now()
                job.status = Job.Status.FAILURE
                job.message = message
                job.save()
