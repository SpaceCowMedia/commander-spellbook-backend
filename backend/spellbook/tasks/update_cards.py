import logging
from django.db.models import Q, Count
from django.tasks import task
from spellbook.models import Card, DEFAULT_BATCH_SIZE
from spellbook.models.variant import Variant
from .scryfall import scryfall, update_cards


logger = logging.getLogger(__name__)


@task
def update_cards_task():
    '''Updates cards using Scryfall/EDHREC bulk data'''
    logger.info('Fetching Scryfall and EDHREC datasets...')
    scryfall_name_db = scryfall()
    logger.info('Fetching Scryfall and EDHREC datasets...done')
    logger.info('Updating cards...')
    cards_to_update = list(Card.objects.all())
    cards_count: dict[int, int] = {
        i: c
        for i, c in Card.objects.annotate(
            updated_variant_count=Count(
                'used_in_variants',
                distinct=True,
                filter=Q(used_in_variants__status__in=Variant.public_statuses())
            ),
        ).values_list('id', 'updated_variant_count')
    }
    cards_to_save = update_cards(
        cards_to_update,
        scryfall_name_db,
        cards_count,
        log=logger.info,
        log_warning=logger.warning,
        log_error=logger.error,
    )
    updated_card_count = len(cards_to_save)
    Card.objects.bulk_update(
        cards_to_save,
        fields=[
            'name',
            'name_unaccented',
            'oracle_id',
            'variant_count',
        ] + Card.scryfall_fields() + Card.playable_fields(),
        batch_size=DEFAULT_BATCH_SIZE,
    )
    logger.info('Updating cards...done')
    if updated_card_count > 0:
        logger.info(f'Successfully updated {updated_card_count} cards')
    else:
        logger.info('No cards to update')
