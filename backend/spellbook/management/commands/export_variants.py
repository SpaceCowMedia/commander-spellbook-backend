import json
import gzip
from pathlib import Path
from django.utils import timezone
from django.contrib.admin.models import LogEntry, ADDITION
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import transaction
from djangorestframework_camel_case.util import camelize
from spellbook.models import Variant, Job, VariantAlias
from spellbook.serializers import VariantSerializer, VariantAliasSerializer
from spellbook.views.variants import VariantViewSet
from spellbook.views.variant_aliases import VariantAliasViewSet
from ..abstract_command import AbstractCommand
from ..s3_upload import upload_json_to_aws

DEFAULT_VARIANTS_FILE_NAME = 'variants.json'


def prepare_variant(variant: Variant):
    return VariantViewSet.serializer_class(variant).data


def prepare_variant_alias(variant_alias: VariantAlias):
    return VariantAliasViewSet.serializer_class(variant_alias).data


class Command(AbstractCommand):
    name = 'export_variants'
    help = 'Exports variants to a JSON file'
    batch_size = 5000

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
        self.log('Fetching variants from db...')
        variants_source = list[Variant]()
        with transaction.atomic(durable=True):
            variants_query = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.public_statuses() + Variant.preview_statuses()))
            for i in range(0, variants_query.count(), self.batch_size):
                variants_source.extend(variants_query[i:i + self.batch_size])
        self.log('Fetching variants from db...done', self.style.SUCCESS)
        self.log('Updating variants preserialized representation...')
        Variant.objects.bulk_serialize(objs=variants_source, serializer=VariantSerializer, batch_size=self.batch_size)
        self.log('Updating variants preserialized representation...done', self.style.SUCCESS)
        self.log('Fetching variant aliases from db...')
        with transaction.atomic(durable=True):
            variants_alias_source = list[VariantAlias](VariantAliasSerializer.prefetch_related(VariantAliasViewSet.queryset))
        self.log('Exporting variants...')
        result = {
            'timestamp': timezone.now().isoformat(),
            'version': settings.VERSION,
            'variants': [prepare_variant(v) for v in variants_source if v.status in Variant.public_statuses()],
            'aliases': [prepare_variant_alias(va) for va in variants_alias_source],
        }
        camelized_json = camelize(result)
        if options['s3']:
            self.log('Uploading to S3...')
            upload_json_to_aws(camelized_json, DEFAULT_VARIANTS_FILE_NAME)
            self.log('Done')
        elif options['file'] is not None:
            output: Path = options['file'].resolve()
            self.log(f'Exporting variants to {output}...')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                json.dump(camelized_json, f)
                json.dump(camelized_json, fz)
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
