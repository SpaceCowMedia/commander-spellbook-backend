import logging
from django.tasks import task
from django.db.models import Subquery, OuterRef, Count, Q
from django.db.models.functions import Coalesce
from django.db import transaction
from spellbook.models import Variant, DEFAULT_BATCH_SIZE
from spellbook.models.combo import Combo
from .edhrec import update_variants, edhrec


logger = logging.getLogger(__name__)


@task
def update_variants_task():
    '''Updates variants using cards and EDHREC data'''
    # Combos
    logger.info('Updating combos...')
    Combo.objects.update(
        variant_count=Coalesce(
            Subquery(
                Variant
                .objects
                .filter(status__in=Variant.public_statuses())
                .filter(of=OuterRef('pk'))
                .order_by()
                .values('of')
                .annotate(total=Count('pk'))
                .values('total'),
            ),
            0,
        ),
    )
    logger.info('Updating combos...done')
    # Variants
    logger.info('Fetching EDHREC dataset...')
    edhrec_variant_db = edhrec()
    logger.info('Fetching Commander Spellbook dataset...')
    variants_query = Variant.recipes_prefetched.all()
    logger.info('Updating variants...')
    updated_variant_count = 0
    variants_count = variants_query.count()
    batch_count = (variants_count + DEFAULT_BATCH_SIZE - 1) // DEFAULT_BATCH_SIZE
    for i in range(0, variants_count, DEFAULT_BATCH_SIZE):
        logger.info(f'Starting batch {i // DEFAULT_BATCH_SIZE + 1}/{batch_count}...')
        with transaction.atomic(durable=True):
            variants = list[Variant](variants_query[i:i + DEFAULT_BATCH_SIZE])
        variants_counts: dict[str, int] = {
            i: c
            for i, c in Variant
            .objects
            .order_by()
            .filter(pk__in=(v.pk for v in variants))
            .annotate(variant_count_updated=Count(
                'of__variants',
                distinct=True,
                filter=Q(of__variants__status__in=Variant.public_statuses()),
            ))
            .values_list('id', 'variant_count_updated')
        }
        variants_to_save = update_variants(
            variants,
            edhrec_variant_db,
            variants_counts,
        )
        updated_variant_count += len(variants_to_save)
        logger.info(f'  Saving {len(variants_to_save)} updated variants...')
        Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields() + ['popularity', 'variant_count'])
        del variants, variants_counts, variants_to_save
    del variants_query
    logger.info(f'Updating variants...done, updated {updated_variant_count} variants')
