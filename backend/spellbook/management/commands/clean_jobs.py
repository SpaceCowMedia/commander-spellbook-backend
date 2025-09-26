from django.core.management.base import CommandParser
from django.utils import timezone
from django.db.models import F, Value
from django.db.models.functions import Concat
from spellbook.models import Job
from ..abstract_command import AbstractCommand


class Command(AbstractCommand):
    name = 'clean_jobs'
    help = 'Clean pending jobs'

    def add_arguments(self, parser: CommandParser):
        super().add_arguments(parser)
        parser.add_argument(
            '--force',
            action='store_true',
            dest='force',
            help='Force clean all pending jobs',
        )

    def handle(self, *args, **options):
        # Handle other pending clean_jobs jobs before running
        Job.objects.filter(status=Job.Status.PENDING, name=self.name).update(status=Job.Status.FAILURE, message='Job was cancelled.', termination=timezone.now())
        super().handle(*args, **options)

    def run(self, *args, **options):
        self.log('Cleaning pending jobs...')
        query = Job.objects.filter(status=Job.Status.PENDING)
        if not options['force']:
            query = query.filter(expected_termination__lt=timezone.now())
        count = query.count()
        if count > 0:
            query.update(status=Job.Status.FAILURE, message=Concat(F('message'), Value('\nJob was cancelled.')), termination=timezone.now())
            self.log(f'{count} pending jobs were cancelled.', self.style.SUCCESS)
        else:
            self.log('No pending jobs found.')
