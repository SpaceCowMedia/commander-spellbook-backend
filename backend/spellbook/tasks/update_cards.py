import logging
from django.tasks import task
from django_tasks import TaskContext
from spellbook.models import Card, DEFAULT_BATCH_SIZE
from .oracle_tags import update_oracle_tags
from .template_matches import update_template_matches
from .scryfall import scryfall, update_cards


logger = logging.getLogger(__name__)


@task(takes_context=True)  # type: ignore[arg-type]
def update_cards_task(context: TaskContext):
    '''Updates cards using Scryfall/EDHREC bulk data'''
    if hasattr(context, 'metadata'):
        context.metadata['log'] = ''
        context.save_metadata()

        def progress(fraction: float):
            context.metadata['progress'] = f'{int(fraction * 100)}/100'
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
        def progress(fraction: float):
            pass

        def log(message: str):
            logger.info(message)

        def log_warning(message: str):
            logger.warning(message)

        def log_error(message: str):
            logger.error(message)
    progress(0)
    log('Fetching Scryfall and EDHREC datasets...')
    scryfall_name_db = scryfall()
    log('Fetching Scryfall and EDHREC datasets...done')
    progress(0.2)
    log('Updating cards...')
    cards_to_update = list(Card.objects.order_by())
    cards_to_save, cards_to_create, cards_to_delete = update_cards(
        cards_to_update,
        scryfall_name_db,
        log=log,
        log_warning=log_warning,
        log_error=log_error,
        progress=lambda fraction: progress(0.2 + fraction * 0.62),
    )
    progress(0.82)
    updated_card_count = len(cards_to_save)
    created_card_count = len(cards_to_create)
    deleted_card_count = len(cards_to_delete)
    Card.objects.filter(pk__in=[card.pk for card in cards_to_delete]).delete()
    Card.objects.bulk_update(
        cards_to_save,
        fields=[
            'name',
            'name_unaccented',
            'oracle_id',
        ] + Card.scryfall_fields() + Card.playable_fields(),
        batch_size=DEFAULT_BATCH_SIZE,
    )
    Card.objects.bulk_create(cards_to_create, batch_size=DEFAULT_BATCH_SIZE)
    log('Updating cards...done')
    progress(0.87)
    log('Updating oracle tags...')
    tags_added, tags_removed = update_oracle_tags(scryfall_name_db)
    log(f'Updating oracle tags...done: {tags_added} added, {tags_removed} removed')
    progress(0.9)
    # what the templates stand for is worked out last: it reads the cards and the tags this job just wrote
    log('Updating what the templates match...')
    matches_added, matches_removed = update_template_matches(log_error=log_error)
    log(f'Updating what the templates match...done: {matches_added} added, {matches_removed} removed')
    progress(1)
    if updated_card_count > 0 or created_card_count > 0 or deleted_card_count > 0:
        log(f'Successfully updated {updated_card_count} cards, added {created_card_count} and removed {deleted_card_count}')
    else:
        log('No cards to update')
