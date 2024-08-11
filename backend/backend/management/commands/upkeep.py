from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Flush expired entities and run upkeep tasks'

    def handle(self, *args, **options):
        self.stdout.write('Flushing expired tokens...')
        call_command('flushexpiredtokens')
        self.stdout.write('Flushing expired sessions...')
        call_command('clearsessions')
        self.stdout.write(self.style.SUCCESS('Done.'))
