import json
import gzip
from pathlib import Path
from django.utils import timezone
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import transaction
from djangorestframework_camel_case.util import camelize
from spellbook.models import Variant, Job, VariantAlias, DEFAULT_BATCH_SIZE
from spellbook.serializers import VariantSerializer, VariantAliasSerializer
from spellbook.views.variants import VariantViewSet
from spellbook.views.variant_aliases import VariantAliasViewSet
from ..abstract_command import AbstractCommand
from ..s3_upload import upload_json_to_aws

DEFAULT_VARIANTS_FILE_NAME = 'variants.json'


def prepare_variant(variant: Variant) -> dict:
    return camelize(VariantViewSet.serializer_class(variant).data)  # type: ignore


def prepare_variant_alias(variant_alias: VariantAlias) -> dict:
    return camelize(VariantAliasViewSet.serializer_class(variant_alias).data)  # type: ignore


class Command(AbstractCommand):
    name = 'export_variants'
    help = 'Exports variants to a JSON file'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--file',
            type=Path,
            dest='file',
            default=settings.STATIC_BULK_FOLDER / DEFAULT_VARIANTS_FILE_NAME
        )
        parser.add_argument(
            '--s3',
            action='store_true',
            dest='s3',
        )

    def run(self, *args, **options):
        self.log('Update preview representations for preview variants...')
        variants_query = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.preview_statuses()))
        variants_count = variants_query.count()
        for i in range(0, variants_count, DEFAULT_BATCH_SIZE):
            with transaction.atomic(durable=True):
                variants_source = list[Variant](variants_query[i:i + DEFAULT_BATCH_SIZE])
            Variant.objects.bulk_serialize(objs=variants_source, serializer=VariantSerializer)
            del variants_source
            self.log(f'  Processed {min(i + DEFAULT_BATCH_SIZE, variants_count)} / {variants_count} preview variants')
        del variants_query
        variants: list[dict | None]
        self.log('Fetching and processing public variants from db...')
        variants_query = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.public_statuses()))
        variants_count = variants_query.count()
        variants: list[dict | None] = [None] * variants_count
        for i in range(0, variants_count, DEFAULT_BATCH_SIZE):
            with transaction.atomic(durable=True):
                variants_source = list[Variant](variants_query[i:i + DEFAULT_BATCH_SIZE])
            Variant.objects.bulk_serialize(objs=variants_source, serializer=VariantSerializer)
            variants[i:i + DEFAULT_BATCH_SIZE] = (prepare_variant(v) for v in variants_source)
            del variants_source
            self.log(f'  Processed {min(i + DEFAULT_BATCH_SIZE, variants_count)} / {variants_count} public variants')
        del variants_query
        self.log('Fetching variant aliases from db...')
        variants_alias_query = VariantAliasSerializer.prefetch_related(VariantAliasViewSet.queryset)
        variants_alias_count = variants_alias_query.count()
        variants_alias: list[dict | None] = [None] * variants_alias_count
        for i in range(0, variants_alias_count, DEFAULT_BATCH_SIZE):
            with transaction.atomic(durable=True):
                variants_alias_source = list[VariantAlias](variants_alias_query[i:i + DEFAULT_BATCH_SIZE])
            variants_alias[i:i + DEFAULT_BATCH_SIZE] = (prepare_variant_alias(va) for va in variants_alias_source)
            del variants_alias_source
            self.log(f'  Processed {min(i + DEFAULT_BATCH_SIZE, variants_alias_count)} / {variants_alias_count} variant aliases')
        del variants_alias_query
        self.log('Exporting variants...')
        result = {
            'timestamp': timezone.now().isoformat(),
            'version': settings.VERSION,
            'variants': variants,
            'aliases': variants_alias,
        }
        if options['s3']:
            self.log('Uploading to S3...')
            upload_json_to_aws(result, DEFAULT_VARIANTS_FILE_NAME)
            self.log('Done')
        elif options['file'] is not None:
            output: Path = options['file'].resolve()
            self.log(f'Exporting variants to {output}...')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                json.dump(result, f)
                json.dump(result, fz)
            self.log('Done')
        else:
            raise Exception('No file specified')
        self.log('Successfully exported %i variants' % len(result['variants']), self.style.SUCCESS)
        if self.job is not None and self.job.started_by is not None:
            LogEntry(
                user=self.job.started_by,
                content_type=ContentType.objects.get_for_model(Job),
                object_id=self.job.id,
                object_repr='Exported Variants',
                action_flag=ADDITION,
            ).save()
