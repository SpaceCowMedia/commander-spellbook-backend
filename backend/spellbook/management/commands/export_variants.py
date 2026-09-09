from django.core.management.base import BaseCommand
from django.tasks import TaskResult
from spellbook.tasks import export_variants_task


class Command(BaseCommand):
    help = 'Exports the variants database to file or an S3 bucket'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '--file',
            action='store_true',
            dest='file',
        )
        parser.add_argument(
            '--s3',
            action='store_true',
            dest='s3',
        )

    def handle(self, *args, **options):
        result: TaskResult = export_variants_task.enqueue(
            file=options['file'],
            s3=options['s3'],
        )
        self.stdout.write(self.style.SUCCESS(f'Enqueued variant export task with id {result.id}.'))
