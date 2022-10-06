from django.utils import timezone
from django.core.management.base import BaseCommand
from spellbook.models import Job


class Command(BaseCommand):
    help = 'Clean pending jobs'

    def handle(self, *args, **options):
        self.stdout.write('Cleaning pending jobs...')
        query = Job.objects.filter(status=Job.Status.PENDING)
        count = query.count()
        if count > 0:
            query.update(status=Job.Status.FAILURE, message='Job was cancelled.', termination=timezone.now())
            now = timezone.now() + timezone.timedelta(seconds=2)
            job = Job(
                name="cancel_jobs",
                expected_termination=now,
                termination=now,
                status=Job.Status.SUCCESS,
                message=f"{count} pending jobs were cancelled.")
            job.save()
            self.stdout.write(self.style.SUCCESS(f"{count} pending jobs were cancelled."))
        else:
            self.stdout.write(self.style.SUCCESS("No pending jobs to cancel."))
