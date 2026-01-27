import logging
from django.tasks import task
from django_tasks import TaskContext
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION
from spellbook.models import Variant
from .utils import task_result_identifier
from spellbook.variants.variants_generator import generate_variants


logger = logging.getLogger(__name__)


@task(takes_context=True)
def generate_variants_task(context: TaskContext, combo: int | None = None, started_by_user_id: int | None = None) -> str:
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
    else:
        def log(message: str):
            logger.info(message)

        def log_error(message: str):
            logger.error(message)

        def progress(current: int, total: int):
            pass
    added, restored, removed = generate_variants(
        combo=combo,
        job=job_id,
        log=log,
        log_error=log_error,
        progress=progress,
    )
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
