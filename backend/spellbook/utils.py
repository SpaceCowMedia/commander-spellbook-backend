from datetime import timedelta
import pathlib
import subprocess
import sys

from .models import Job
from django.db.models import Avg, F
from django.utils import timezone


def launch_command_async(command: str, args: list[str]=[]):
    manage_py_path = pathlib.Path(__file__).parent.parent / 'manage.py'
    args = ['python', manage_py_path.resolve(), command] + args
    if sys.platform == "win32":
        subprocess.Popen(
            args=args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        subprocess.Popen(args=args)


def launch_job_command(command: str, duration: timedelta, user) -> bool:
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
        launch_command_async(command, ['--id', str(job.id)])
        return True
    return False
