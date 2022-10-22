from datetime import timedelta
import pathlib
import subprocess
import sys
from django.utils import timezone
from django.core.management import call_command
from django.db.models import Avg, F
from .models import Job
from django.conf import settings

ASYNC_MODE = False


def launch_command_async(command: str, args: list[str] = []):
    manage_py_path = pathlib.Path(__file__).parent.parent / 'manage.py'
    args = ['python', manage_py_path.resolve(), command] + args
    if sys.platform == "win32":
        subprocess.Popen(
            args=args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        subprocess.Popen(args=args)


def launch_job_command(command: str, duration: timedelta, user, args: list[str] = []) -> bool:
    """
    Launch a command asynchronously and create a Job object to track it.
    The command must be a management command that can take a --id parameter with the Job id.
    Returns true if the command was launched, false if there is already a job.
    """
    past_runs_duration = Job.objects \
        .filter(name=command, status=Job.Status.SUCCESS) \
        .order_by('-created')[:5] \
        .annotate(duration=F('termination') - F('created')) \
        .aggregate(average_duration=Avg('duration'))['average_duration']
    if past_runs_duration is None:
        past_runs_duration = duration

    job = Job.start(
        name=command,
        duration=past_runs_duration * 1.5,
        user=user)
    if job is not None:
        try:
            if ASYNC_MODE:
                launch_command_async(command, ['--id', str(job.id)] + args)
            else:
                call_command(command, *args, id=job.id)
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = str(e)
            job.save()
            if settings.DEBUG:
                raise e
        return True
    return False
