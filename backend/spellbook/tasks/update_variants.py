import logging
from django.tasks import task
from django_tasks import TaskContext
from django.db import transaction
from spellbook.models import Variant, DEFAULT_BATCH_SIZE, recompute_all_counts
from .edhrec import update_variants, edhrec


logger = logging.getLogger(__name__)


@task(takes_context=True)  # type: ignore[arg-type]
def update_variants_task(context: TaskContext):
    '''Updates variants using cards and EDHREC data'''
    if hasattr(context, 'metadata'):
        def progress(fraction: float):
            context.metadata['progress'] = f'{int(fraction * 100)}/100'
            context.save_metadata()

        def log(message: str):
            logger.info(message)
            context.metadata['log'] = message
            context.save_metadata()
    else:
        def progress(fraction: float):
            pass

        def log(message: str):
            logger.info(message)
    progress(0)
    # Variants
    log('Fetching EDHREC dataset...')
    edhrec_variant_db = edhrec()
    progress(0.1)
    log('Fetching Commander Spellbook dataset...')
    variant_ids = list(Variant.objects.order_by().values_list('pk', flat=True))
    variant_count = len(variant_ids)
    log('Updating variants...')
    variant_processed = 0
    updated_variant_count = 0
    batch_count = (variant_count + DEFAULT_BATCH_SIZE - 1) // DEFAULT_BATCH_SIZE
    for i in range(0, variant_count, DEFAULT_BATCH_SIZE):
        log(f'Starting batch {i // DEFAULT_BATCH_SIZE + 1}/{batch_count}...')
        batch = variant_ids[i:i + DEFAULT_BATCH_SIZE]
        with transaction.atomic(durable=True):
            variants = list[Variant](Variant.recipes_prefetched.filter(pk__in=batch).order_by())
        variants_to_save = update_variants(
            variants,
            edhrec_variant_db,
        )
        updated_variant_count += len(variants_to_save)
        log(f'  Saving {len(variants_to_save)} updated variants...')
        Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields() + ['popularity'])
        variant_processed += len(variants)
        log(f'  Processed {variant_processed} / {variant_count} variants')
        progress(0.1 + variant_processed / variant_count * 0.9)
        del variants, variants_to_save
    del variant_ids
    log(f'Updating variants...done, updated {updated_variant_count} variants')
    # The counters are maintained as their inputs change, so this only has to confirm it: a rebuild
    # of the whole dataset is a second of set based work, and anything it finds is a bug in a write
    # path that failed to report what it touched.
    log('Verifying variant counts...')
    drifted = recompute_all_counts()
    if drifted:
        logger.error(f'Repaired {drifted} rows whose denormalized counts had drifted')
    log(f'Verifying variant counts...done, repaired {drifted} rows')
