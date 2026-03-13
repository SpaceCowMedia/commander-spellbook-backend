import logging
from django.db.models import Q, Count
from django.tasks import task
from django_tasks import TaskContext
from spellbook.models import Card, DEFAULT_BATCH_SIZE
from spellbook.models.variant import Variant
from .scryfall import scryfall, update_cards


logger = logging.getLogger(__name__)


@task(takes_context=True)
def update_cards_task(context: TaskContext):
    '''Updates cards using Scryfall/EDHREC bulk data'''
    if hasattr(context, 'metadata'):
        context.metadata['log'] = ''
        context.save_metadata()

        def log(message: str):
            logger.info(message)
            context.metadata['log'] = message
            context.save_metadata()

        def log_warning(message: str):
            logger.warning(message)
            context.metadata['log'] = message
            context.save_metadata()

        def log_error(message: str):
            logger.error(message)
            context.metadata['log'] = message
            context.save_metadata()
    else:
        def log(message: str):
            logger.info(message)

        def log_warning(message: str):
            logger.warning(message)

        def log_error(message: str):
            logger.error(message)
    log('Fetching Scryfall and EDHREC datasets...')
    scryfall_name_db = scryfall()
    log('Fetching Scryfall and EDHREC datasets...done')
    log('Updating cards...')
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
        log=log,
        log_warning=log_warning,
        log_error=log_error,
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
    log('Updating cards...done')
    if updated_card_count > 0:
        log(f'Successfully updated {updated_card_count} cards')
    else:
        log('No cards to update')
