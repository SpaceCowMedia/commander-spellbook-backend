import sys
import subprocess
import pathlib
import logging
from django.utils import timezone
from django.core.management import call_command
from django.conf import settings
from django.db import transaction
from django.contrib.auth.models import User
from common.stream import StreamToLogger
from spellbook.models import Job


def launch_command_async(command: str, args: list[str] = []):
    manage_py_path = pathlib.Path(__file__).parent.parent / 'manage.py'
    avoid_pypy = command in ['runserver', 'shell', 'export_variants']
    interpreter = 'pypy' if not avoid_pypy and settings.PYPY_AVAILABLE else 'python'
    args = [interpreter, manage_py_path.resolve(), command] + args
    if sys.platform == "win32":
        subprocess.Popen(
            args=args,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        subprocess.Popen(args=['timeout', str(Job.TIMEOUT.total_seconds())] + args)


def launch_job_command(command: str, user: User | None = None, args: list[str] = [], allow_multiples: bool = False, group: str | None = None, background: bool = True) -> Job | None:
    """
    Launch a command asynchronously and create a Job object to track it.
    The command must be a management command that can take a --id parameter with the Job id.
    Returns true if the command was launched, false in case of errors or
    if there is already a job ongoing with the same name, unless allow_multiples is passed.
    """
    job = Job.start(
        name=command,
        args=args,
        group=group,
        duration=None,
        user=user,
        allow_multiples=allow_multiples,
    )
    if job is not None:
        logger = logging.getLogger(command)
        try:
            if background and not settings.DEBUG:
                launch_command_async(command, ['--id', str(job.id)] + args)
            else:
                call_command(
                    command,
                    *args,
                    id=job.id,
                    stdout=StreamToLogger(logger, logging.INFO),
                    stderr=StreamToLogger(logger, logging.ERROR)
                )
                job.refresh_from_db()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = str(e)
            job.save()
            logger.error(e)
            if settings.DEBUG:
                raise e
    return job


def log_into_job(job: Job | None, message: str, reset=False):
    logging.info(message)
    if job:
        if reset:
            job.message = message
        else:
            job.message += message + '\n'
        with transaction.atomic():
            job.save()
