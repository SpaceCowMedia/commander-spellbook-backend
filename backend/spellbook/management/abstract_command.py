import traceback
from platform import python_implementation
from time import sleep
from django.utils import timezone
from django.core.management.base import BaseCommand, CommandParser, CommandError
from django.db import OperationalError
from django.conf import settings
from discord_webhook import DiscordWebhook
from text_utils import discord_chunk
from spellbook.models import Job
from spellbook.utils import log_into_job


class AbstractCommand(BaseCommand):
    name = 'abstract_command'
    job: Job | None = None
    interpreter: str = python_implementation()
    args: list[str] = []

    def log(self, message, style=lambda x: x):
        self.stdout.write(style(message))
        if self.job is not None:
            log_into_job(self.job, message)

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--id',
            type=int,
            dest='job_id',
        )

    def run_from_argv(self, argv: list[str]):
        self.args = argv[2:]
        return super().run_from_argv(argv)

    def handle(self, *args, **options):
        self.job = Job.get_or_start(options['job_id'], self.name, self.args)
        if self.job is None and options['job_id'] is not None:
            raise CommandError('Job with id %s does not exist' % options['job_id'])
        elif self.job is None:
            raise CommandError(f'Job with name {self.name} already running')
        try:
            self.log(f'Running {self.name} ({settings.VERSION}) using {self.interpreter}...')
            self.run(*args, **options)
            self.log(f'{self.name} finished successfully.', self.style.SUCCESS)
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

    def discord_webhook(self, content: str):
        if settings.DISCORD_WEBHOOK_URL:
            messages = discord_chunk(content)
            for message in messages:
                webhook = DiscordWebhook(url=settings.DISCORD_WEBHOOK_URL, content=message)
                response = webhook.execute()
                if response.ok:
                    self.log('Webhook sent', self.style.SUCCESS)
                else:
                    self.log(f'Webhook failed with status code {response.status_code}:\n{response.content.decode()}', self.style.ERROR)
                    raise Exception('Webhook failed')
        else:
            self.log('No Discord Webhook set in settings', self.style.ERROR)
