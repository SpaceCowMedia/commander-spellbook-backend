from django.core.management.base import BaseCommand
from django.tasks import TaskResult
from spellbook.tasks import update_cards_task


class Command(BaseCommand):
    help = 'Updates the cards database'

    def handle(self, *args, **options):
        result: TaskResult = update_cards_task.enqueue()
        self.stdout.write(self.style.SUCCESS(f'Enqueued card update task with id {result.id}.'))
