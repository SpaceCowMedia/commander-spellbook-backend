import json
import gzip
from pathlib import Path
from django.utils import timezone
from django.core.management.base import BaseCommand
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
            default=Path('/home/app/web/staticfiles/bulk/variants.json')
        )

    def handle(self, *args, **options):
        job = Job(name='export_variants', expected_termination=timezone.now() + timezone.timedelta(minutes=1))
        job.save()
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
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            v = result['variants']
            job.message = f'Successfully exported {len(v)} variants'
            job.save()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = f'Failed to export variants: {e}'
            job.save()
            raise e
