import logging
from django.tasks import task, TaskContext
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry, ADDITION
from spellbook.models import Variant
from .utils import task_result_identifier
from spellbook.variants.variants_generator import generate_variants


logger = logging.getLogger(__name__)


@task(takes_context=True)
def generate_variants_task(context: TaskContext, combo: int | None = None, started_by_user_id: int | None = None) -> str:
    job_id = task_result_identifier(context.task_result)
    added, restored, removed = generate_variants(combo=combo, job=job_id)
    if added == 0 and removed == 0 and restored == 0:
        message = 'Variants are already synced with'
    else:
        message = f'Generated {added} new variants, restored {restored} variants, removed {removed} variants for'
    message += ' all combos'
    logger.info(message)
    if started_by_user_id is not None:
        LogEntry(
            user_id=started_by_user_id,
            content_type=ContentType.objects.get_for_model(Variant),
            object_id=None,
            object_repr='Generated Variants',
            action_flag=ADDITION,
        ).save()
    return message
