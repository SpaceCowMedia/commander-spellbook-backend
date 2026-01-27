from django.tasks import TaskResult
from django.conf import settings


def task_result_identifier(task_result: TaskResult) -> str:
    backend = settings.TASKS[task_result.backend]['BACKEND']
    return f'{backend.split('.', 1)[0]}_{task_result.id}'
