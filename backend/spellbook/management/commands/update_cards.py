from django.core.management.base import BaseCommand
from spellbook.tasks import update_cards_task


class Command(BaseCommand):
    help = 'Updates the cards database'

    def handle(self, *args, **options):
        update_cards_task.enqueue()
