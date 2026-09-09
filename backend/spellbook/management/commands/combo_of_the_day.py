from django.core.management.base import BaseCommand
from django.tasks import TaskResult
from spellbook.tasks import combo_of_the_day_task


class Command(BaseCommand):
    help = 'Replaces the combo of the day'

    def handle(self, *args, **options):
        result: TaskResult = combo_of_the_day_task.enqueue()
        self.stdout.write(self.style.SUCCESS(f'Enqueued combo of the day task with id {result.id}.'))
