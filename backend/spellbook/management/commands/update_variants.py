from django.core.management.base import BaseCommand
from spellbook.tasks import update_variants_task


class Command(BaseCommand):
    help = 'Updates the variants database'

    def handle(self, *args, **options):
        update_variants_task.enqueue()
