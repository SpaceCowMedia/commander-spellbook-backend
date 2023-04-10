import sys
import subprocess
import pathlib
from datetime import timedelta
from django.utils import timezone
from django.core.management import call_command
from django.db.models import Avg, F
from django.conf import settings
from spellbook.models import Job


def launch_command_async(command: str, args: list[str] = []):
    manage_py_path = pathlib.Path(__file__).parent.parent / 'manage.py'
    args = ['python', manage_py_path.resolve(), command] + args
    if sys.platform == "win32":
        subprocess.Popen(
            args=args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        subprocess.Popen(args=args)


def launch_job_command(command: str, user, args: list[str] = []) -> bool:
    """
    Launch a command asynchronously and create a Job object to track it.
    The command must be a management command that can take a --id parameter with the Job id.
    Returns true if the command was launched, false if there is already a job.
    """
    job = Job.start(
        name=command,
        duration=None,
        user=user)
    if job is not None:
        try:
            if settings.ASYNC_GENERATION:
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
