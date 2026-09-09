from django.core.management.base import BaseCommand
from django.tasks import TaskResult
from spellbook.tasks import update_variants_task


class Command(BaseCommand):
    help = 'Updates the variants database'

    def handle(self, *args, **options):
        result: TaskResult = update_variants_task.enqueue()
        self.stdout.write(self.style.SUCCESS(f'Enqueued variant update task with id {result.id}.'))
