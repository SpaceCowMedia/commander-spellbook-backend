from django.utils import timezone
from spellbook.models import Job
from ..abstract_command import AbstractCommand


class Command(AbstractCommand):
    name = 'clean_jobs'
    help = 'Clean pending jobs'

    def run(self, *args, **options):
        self.log('Cleaning pending jobs...')
        query = Job.objects.filter(status=Job.Status.PENDING)
        count = query.count()
        if count > 0:
            query.update(status=Job.Status.FAILURE, message='Job was cancelled.', termination=timezone.now())
            self.log(f'{count} pending jobs were cancelled.', self.style.SUCCESS)
        else:
            self.log('No pending jobs found.')
