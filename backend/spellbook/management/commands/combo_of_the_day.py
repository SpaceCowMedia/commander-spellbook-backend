from django.core.management.base import BaseCommand
from spellbook.tasks import combo_of_the_day_task


class Command(BaseCommand):
    help = 'Replaces the combo of the day'

    def handle(self, *args, **options):
        combo_of_the_day_task.enqueue()
