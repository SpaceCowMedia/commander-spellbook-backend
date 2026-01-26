from django.tasks import TaskResult


def task_result_identifier(task_result: TaskResult) -> str:
    return f'{task_result.backend.split('.', 1)[0]}_{task_result.id}'
