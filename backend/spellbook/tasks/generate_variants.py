import logging
from django.tasks import task
from django_tasks import TaskContext
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION
from django.db.models import Subquery, OuterRef, Count
from django.db.models.functions import Coalesce
from spellbook.models import Variant
from spellbook.models.combo import Combo
from .utils import task_result_identifier
from spellbook.variants.variants_generator import generate_variants


logger = logging.getLogger(__name__)


def update_combo_variant_counts() -> int:
    '''Refreshes Combo.variant_count with how many variants each combo generates.

    Every variant is counted, whatever its status: the count is an editing aid telling how much
    a combo expands into, so a combo whose variants have just been generated (and are therefore
    all in the NEW status, awaiting review) has to show them right away.
    '''
    return Combo.objects.update(
        variant_count=Coalesce(
            Subquery(
                Variant
                .objects
                .filter(of=OuterRef('pk'))
                .order_by()
                .values('of')
                .annotate(total=Count('pk'))
                .values('total'),
            ),
            0,
        ),
    )


@task(takes_context=True)  # type: ignore[arg-type]
def generate_variants_task(context: TaskContext, combo: int | None = None, started_by_user_id: int | None = None, incremental: bool = False) -> str:
    job_id = task_result_identifier(context.task_result)  # type: ignore
    if hasattr(context, 'metadata'):
        context.metadata['generation_id'] = job_id
        context.metadata['progress'] = '0/1'
        context.metadata['log'] = ''
        context.save_metadata()

        def log(message: str):
            logger.info(message)
            context.metadata['log'] = message
            context.save_metadata()

        def log_error(message: str):
            logger.error(message)
            context.metadata['log'] = message
            context.save_metadata()

        def progress(current: int, total: int):
            context.metadata['progress'] = f'{current}/{total}'
            context.save_metadata()

        def metadata(key: str, value: object):
            context.metadata[key] = value
            context.save_metadata()
    else:
        def log(message: str):
            logger.info(message)

        def log_error(message: str):
            logger.error(message)

        def progress(current: int, total: int):
            pass

        def metadata(key: str, value: object):
            pass
    added, restored, removed = generate_variants(
        combo=combo,
        job=job_id,
        log=log,
        log_error=log_error,
        progress=progress,
        metadata=metadata,
        incremental=incremental,
    )
    log('Updating combo variant counts...')
    update_combo_variant_counts()
    if added == 0 and removed == 0 and restored == 0:
        message = 'Variants are already synced with'
    else:
        message = f'Generated {added} new variants, restored {restored} variants, removed {removed} variants for'
    message += ' all combos'
    logger.info(message)
    if hasattr(context, 'metadata'):
        context.metadata['variant_count'] = added + restored
        context.metadata['log'] = message
    if started_by_user_id is not None:
        LogEntry(
            user_id=started_by_user_id,
            content_type=ContentType.objects.get_for_model(Variant),
            object_id=None,
            object_repr='Generated Variants',
            action_flag=ADDITION,
        ).save()
    return message
