import traceback
from time import sleep
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.db import OperationalError
from spellbook.models import Job
from spellbook.utils import log_into_job


class AbstractCommand(BaseCommand):
    name = 'abstract_command'
    job: Job | None = None

    def log(self, message, style=lambda x: x):
        self.stdout.write(style(message))
        if self.job is not None:
            log_into_job(self.job, message)

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )

    def handle(self, *args, **options):
        self.job = Job.get_or_start(self.name, options['job_id'])
        if self.job is None and options['job_id'] is not None:
            raise CommandError('Job with id %s does not exist' % options['job_id'])
        elif self.job is None:
            raise CommandError('Job with name %s already running' % self.name)
        try:
            self.log('Running %s...' % self.name)
            self.run(*args, **options)
            self.log('%s finished successfully.' % self.name, self.style.SUCCESS)
            self.job.termination = timezone.now()
            self.job.status = Job.Status.SUCCESS
            self.job.save()
        except OperationalError as e:
            termination = timezone.now()
            for _ in range(6):
                sleep(10)
                try:
                    self.log(f'Error while running {self.name}: {e}', self.style.ERROR)
                    self.job.termination = termination
                    self.job.status = Job.Status.FAILURE
                    self.job.save()
                    break
                except OperationalError:
                    pass
        except Exception as e:
            self.log(f'Error while running {self.name}: {e}', self.style.ERROR)
            self.log(traceback.format_exc(), self.style.ERROR)
            self.job.termination = timezone.now()
            self.job.status = Job.Status.FAILURE
            self.job.save()

    def run(self, *args, **options):
        raise NotImplementedError('AbstractCommand.run() must be implemented in subclasses')
