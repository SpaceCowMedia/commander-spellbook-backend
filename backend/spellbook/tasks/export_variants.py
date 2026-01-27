import json
import gzip
import logging
from pathlib import Path
from django.utils import timezone
from django.tasks import task
from django.conf import settings
from django.db import transaction
from django_tasks import TaskContext
from djangorestframework_camel_case.util import camelize
from spellbook.models import Variant, VariantAlias, DEFAULT_BATCH_SIZE
from spellbook.serializers import VariantSerializer, VariantAliasSerializer
from spellbook.views.variants import VariantViewSet
from spellbook.views.variant_aliases import VariantAliasViewSet
from .s3_upload import upload_json_to_aws


def prepare_variant(variant: Variant) -> dict:
    return camelize(VariantViewSet.serializer_class(variant).data)  # type: ignore


def prepare_variant_alias(variant_alias: VariantAlias) -> dict:
    return camelize(VariantAliasViewSet.serializer_class(variant_alias).data)  # type: ignore


logger = logging.getLogger(__name__)


DEFAULT_VARIANTS_FILE_NAME = 'variants.json'


@task(takes_context=True)
def export_variants_task(context: TaskContext, file: bool = False, s3: bool = False):
    if hasattr(context, 'metadata'):
        def progress(fraction: float):
            context.metadata['progress'] = f'{int(fraction * 100)}/100'
            context.save_metadata()
    else:
        def progress(fraction: float):
            pass
    preview_variants_query = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.preview_statuses()))
    preview_variants_count = preview_variants_query.count()
    public_variants_query = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.public_statuses()))
    public_variants_count = public_variants_query.count()
    variants_alias_query = VariantAliasSerializer.prefetch_related(VariantAliasViewSet.queryset)
    variants_alias_count = variants_alias_query.count()
    total_progress = (preview_variants_count + public_variants_count + variants_alias_count) or 1
    current_progress = 0
    preprocess_multiplier = 0.6
    logger.info('Update preview representations for preview variants...')
    progress(current_progress / total_progress * preprocess_multiplier)
    for i in range(0, preview_variants_count, DEFAULT_BATCH_SIZE):
        with transaction.atomic(durable=True):
            variants_source = list[Variant](preview_variants_query[i:i + DEFAULT_BATCH_SIZE])
        Variant.objects.bulk_serialize(objs=variants_source, serializer=VariantSerializer)
        current_progress += len(variants_source)
        del variants_source
        logger.info(f'  Processed {min(i + DEFAULT_BATCH_SIZE, preview_variants_count)} / {preview_variants_count} preview variants')
        progress(current_progress / total_progress * preprocess_multiplier)
    del preview_variants_query
    variants: list[dict | None]
    logger.info('Fetching and processing public variants from db...')
    progress(current_progress / total_progress * preprocess_multiplier)
    variants: list[dict | None] = [None] * public_variants_count
    for i in range(0, public_variants_count, DEFAULT_BATCH_SIZE):
        with transaction.atomic(durable=True):
            variants_source = list[Variant](public_variants_query[i:i + DEFAULT_BATCH_SIZE])
        Variant.objects.bulk_serialize(objs=variants_source, serializer=VariantSerializer)
        variants[i:i + DEFAULT_BATCH_SIZE] = (prepare_variant(v) for v in variants_source)
        current_progress += len(variants_source)
        del variants_source
        logger.info(f'  Processed {min(i + DEFAULT_BATCH_SIZE, public_variants_count)} / {public_variants_count} public variants')
        progress(current_progress / total_progress * preprocess_multiplier)
    del public_variants_query
    logger.info('Fetching variant aliases from db...')
    progress(current_progress / total_progress * preprocess_multiplier)
    variants_alias: list[dict | None] = [None] * variants_alias_count
    for i in range(0, variants_alias_count, DEFAULT_BATCH_SIZE):
        with transaction.atomic(durable=True):
            variants_alias_source = list[VariantAlias](variants_alias_query[i:i + DEFAULT_BATCH_SIZE])
        variants_alias[i:i + DEFAULT_BATCH_SIZE] = (prepare_variant_alias(va) for va in variants_alias_source)
        current_progress += len(variants_alias_source)
        del variants_alias_source
        logger.info(f'  Processed {min(i + DEFAULT_BATCH_SIZE, variants_alias_count)} / {variants_alias_count} variant aliases')
        progress(current_progress / total_progress * preprocess_multiplier)
    del variants_alias_query
    logger.info('Exporting variants...')
    result = {
        'timestamp': timezone.now().isoformat(),
        'version': settings.VERSION,
        'variants': variants,
        'aliases': variants_alias,
    }
    progress(preprocess_multiplier)
    if s3:
        logger.info('Uploading to S3...')
        upload_json_to_aws(result, DEFAULT_VARIANTS_FILE_NAME)
        logger.info('Done')
    elif file is not None:
        output: Path = (settings.STATIC_BULK_FOLDER / DEFAULT_VARIANTS_FILE_NAME).resolve()
        logger.info(f'Exporting variants to {output}...')
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
            json.dump(result, f)
            json.dump(result, fz)
        logger.info('Done')
    else:
        raise Exception('No file specified')
    logger.info('Successfully exported %i variants', len(result['variants']))
    progress(1.0)
    return f'Successfully exported {len(result["variants"])} variants'
