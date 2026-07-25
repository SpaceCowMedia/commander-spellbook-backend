import gzip
import io
import json
import logging
import multiprocessing
import multiprocessing.pool
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar
from django.utils import timezone
from django.tasks import task
from django.conf import settings
from django.db import connection, connections, transaction
from django.db.models import Model, QuerySet
from django_tasks import TaskContext
from djangorestframework_camel_case.util import camelize
from multiprocessing_utils import parallelism_is_available, resolve_workers, split_into_chunks
from spellbook.models import Variant, VariantAlias, DEFAULT_BATCH_SIZE
from spellbook.serializers import VariantSerializer, VariantAliasSerializer
from spellbook.views.variants import VariantViewSet
from spellbook.views.variant_aliases import VariantAliasViewSet
from .s3_upload import upload_json_to_aws, upload_gzipped_json_to_aws


logger = logging.getLogger(__name__)


DEFAULT_VARIANTS_FILE_NAME = 'variants.json'

# Parallelism is only worth its overhead above this workload size
MIN_OBJECTS_FOR_PARALLELISM = 2048

SERIALIZATION_PROGRESS_SHARE = 0.6

ProgressFunction = Callable[[float], None]
CountFunction = Callable[[int], None]

_M = TypeVar('_M', bound=Model)


def prepare_variant(variant: Variant) -> dict:
    return camelize(VariantViewSet.serializer_class(variant).data)  # type: ignore


def prepare_variant_alias(variant_alias: VariantAlias) -> dict:
    return camelize(VariantAliasViewSet.serializer_class(variant_alias).data)  # type: ignore


def json_array_items(objects: list[dict]) -> str:
    return json.dumps(objects)[1:-1]


def join_items(items: Iterable[str]) -> str:
    return ','.join(item for item in items if item)


def fetch_in_id_order(queryset: QuerySet[_M], ids: Sequence[str]) -> list[_M]:
    '''Fetches the rows with the given primary keys, in the very order of the given ids.

    Batching by primary key, instead of slicing an ordered queryset, spares the database
    the full sort that every single offset paginated batch would otherwise require.
    '''
    with transaction.atomic(durable=True):
        objects = {o.pk: o for o in queryset.filter(pk__in=ids).order_by()}
    return [objects[id] for id in ids if id in objects]


def serialize_variants_chunk(ids: list[str], export: bool, progress: CountFunction) -> Iterable[str]:
    for i in range(0, len(ids), DEFAULT_BATCH_SIZE):
        batch = ids[i:i + DEFAULT_BATCH_SIZE]
        variants = fetch_in_id_order(VariantSerializer.prefetch_related(Variant.objects.all()), batch)
        Variant.objects.bulk_serialize(objs=variants, serializer=VariantSerializer)
        if export:
            yield json_array_items([prepare_variant(v) for v in variants])
        del variants
        progress(len(batch))


def refresh_variants_chunk(ids: list[str], progress: CountFunction = lambda _: None) -> str:
    return ''.join(serialize_variants_chunk(ids, export=False, progress=progress))


def export_variants_chunk(ids: list[str], progress: CountFunction = lambda _: None) -> str:
    return join_items(serialize_variants_chunk(ids, export=True, progress=progress))


def export_variant_aliases_chunk(ids: list[str], progress: CountFunction = lambda _: None) -> str:
    def items() -> Iterable[str]:
        for i in range(0, len(ids), DEFAULT_BATCH_SIZE):
            batch = ids[i:i + DEFAULT_BATCH_SIZE]
            aliases = fetch_in_id_order(VariantAliasSerializer.prefetch_related(VariantAliasViewSet.queryset), batch)
            yield json_array_items([prepare_variant_alias(a) for a in aliases])
            progress(len(batch))
    return join_items(items())


def parallelism_is_worth_it(objects: int, workers: int) -> bool:
    return workers > 1 \
        and objects >= MIN_OBJECTS_FOR_PARALLELISM \
        and parallelism_is_available() \
        and not connection.in_atomic_block


def map_chunks(
    worker: Callable[..., str],
    ids: list[str],
    workers: int,
    progress: CountFunction,
) -> list[str]:
    if parallelism_is_worth_it(len(ids), workers):
        chunks = split_into_chunks(ids, workers)
        logger.info(f'  Processing {len(ids)} objects in {len(chunks)} chunks with {workers} workers...')
        # The forked workers query the database on their own, so the parent closes its
        # connections before forking: both sides transparently reconnect when needed
        connections.close_all()
        context = multiprocessing.get_context('fork')
        with context.Pool(processes=min(workers, len(chunks))) as pool:
            result = list[str]()
            for chunk, items in zip(chunks, pool.imap(worker, chunks)):
                result.append(items)
                progress(len(chunk))
            return result
    return [worker(ids, progress)]


def json_array(chunks: Iterable[str]) -> Iterable[str]:
    yield '['
    first = True
    for chunk in chunks:
        if not chunk:
            continue
        if not first:
            yield ','
        yield chunk
        first = False
    yield ']'


def build_document(variants: list[str], aliases: list[str]) -> list[str]:
    return [
        '{"timestamp": ', json.dumps(timezone.now().isoformat()),
        ', "version": ', json.dumps(settings.VERSION),
        ', "variants": ', *json_array(variants),
        ', "aliases": ', *json_array(aliases),
        '}',
    ]


# Document parts inherited by the forked worker performing the compression
document_parts: list[str] = []


def compress_document_to_file(destination: str) -> None:
    with gzip.open(destination, mode='wt', encoding='utf8') as f:
        for part in document_parts:
            f.write(part)


def compress_document(_: None = None) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode='wb') as f:
        for part in document_parts:
            f.write(part.encode('utf8'))
    return buffer.getvalue()


def write_document(parts: list[str], output: Path) -> None:
    with output.open('w', encoding='utf8') as f:
        for part in parts:
            f.write(part)


def fork_compression(workers: int) -> multiprocessing.pool.Pool | None:
    '''Forks a single worker compressing the document, so that compression overlaps with writing or uploading it.

    The forked worker never touches the inherited database connections,
    so they can be safely left open in the parent process.
    '''
    if workers <= 1 or not parallelism_is_available():
        return None
    return multiprocessing.get_context('fork').Pool(processes=1)


def export_to_file(parts: list[str], output: Path, workers: int) -> None:
    global document_parts
    document_parts = parts
    output.parent.mkdir(parents=True, exist_ok=True)
    compressed_output = str(output) + '.gz'
    try:
        pool = fork_compression(workers)
        if pool is None:
            write_document(parts, output)
            compress_document_to_file(compressed_output)
            return
        with pool:
            compression = pool.apply_async(compress_document_to_file, (compressed_output,))
            write_document(parts, output)
            compression.get()
    finally:
        document_parts = []


def export_to_s3(parts: list[str], workers: int) -> None:
    global document_parts
    document_parts = parts
    try:
        pool = fork_compression(workers)
        if pool is None:
            document = ''.join(parts)
            upload_json_to_aws(document, DEFAULT_VARIANTS_FILE_NAME)
            upload_gzipped_json_to_aws(gzip.compress(document.encode('utf8')), DEFAULT_VARIANTS_FILE_NAME + '.gz')
            return
        with pool:
            compression = pool.apply_async(compress_document)
            upload_json_to_aws(''.join(parts), DEFAULT_VARIANTS_FILE_NAME)
            upload_gzipped_json_to_aws(compression.get(), DEFAULT_VARIANTS_FILE_NAME + '.gz')
    finally:
        document_parts = []


def export_variants(
    file: bool = False,
    s3: bool = False,
    progress: ProgressFunction = lambda fraction: None,
    workers: int | None = None,
) -> int:
    workers = resolve_workers(workers)
    progress(0)
    preview_ids = list(Variant.objects.filter(status__in=Variant.preview_statuses()).values_list('id', flat=True))
    public_ids = list(Variant.objects.filter(status__in=Variant.public_statuses()).values_list('id', flat=True))
    aliases_ids = list(VariantAliasViewSet.queryset.values_list('id', flat=True))
    total = (len(preview_ids) + len(public_ids) + len(aliases_ids)) or 1
    processed = 0

    def report(count: int) -> None:
        nonlocal processed
        processed += count
        logger.info(f'  Processed {processed} / {total} objects')
        progress(processed / total * SERIALIZATION_PROGRESS_SHARE)
    logger.info(f'Updating the cached representation of {len(preview_ids)} preview variants...')
    map_chunks(refresh_variants_chunk, preview_ids, workers, report)
    logger.info(f'Fetching and processing {len(public_ids)} public variants from db...')
    variants = map_chunks(export_variants_chunk, public_ids, workers, report)
    logger.info(f'Fetching {len(aliases_ids)} variant aliases from db...')
    aliases = map_chunks(export_variant_aliases_chunk, aliases_ids, workers, report)
    progress(SERIALIZATION_PROGRESS_SHARE)
    logger.info('Exporting variants...')
    parts = build_document(variants, aliases)
    del variants, aliases
    if s3:
        logger.info('Uploading to S3...')
        export_to_s3(parts, workers)
        logger.info('Done')
    elif file is not None:
        output: Path = (settings.STATIC_BULK_FOLDER / DEFAULT_VARIANTS_FILE_NAME).resolve()
        logger.info(f'Exporting variants to {output}...')
        export_to_file(parts, output, workers)
        logger.info('Done')
    else:
        raise Exception('No file specified')
    logger.info('Successfully exported %i variants', len(public_ids))
    progress(1.0)
    return len(public_ids)


@task(takes_context=True)  # type: ignore[arg-type]
def export_variants_task(context: TaskContext, file: bool = False, s3: bool = False):
    if hasattr(context, 'metadata'):
        def progress(fraction: float):
            context.metadata['progress'] = f'{int(fraction * 100)}/100'
            context.save_metadata()
    else:
        def progress(fraction: float):
            pass
    exported = export_variants(file=file, s3=s3, progress=progress)
    return f'Successfully exported {exported} variants'
