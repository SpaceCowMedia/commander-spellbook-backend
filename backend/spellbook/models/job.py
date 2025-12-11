import logging
from django.utils import timezone
from django.db import models, transaction, OperationalError
from django.contrib.auth.models import User
from django.conf import settings


class Job(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'S'
        FAILURE = 'F'
        PENDING = 'P'
    id: int
    name = models.CharField(max_length=255, blank=False, verbose_name='name of job')
    args = models.JSONField(default=list, blank=True, verbose_name='arguments for job')
    group = models.CharField(max_length=255, blank=True, null=True, verbose_name='group of job')
    created = models.DateTimeField(auto_now_add=True, blank=False)
    expected_termination = models.DateTimeField(blank=False)
    termination = models.DateTimeField(blank=True, null=True)
    status = models.CharField(choices=Status.choices, default=Status.PENDING, max_length=2, blank=False)
    message = models.TextField(blank=True)
    started_by = models.ForeignKey(
        to=User,
        related_name='started_jobs',
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text='User that started this job',
    )
    version = models.CharField(max_length=50, blank=False, verbose_name='application version at job start')

    TIMEOUT = timezone.timedelta(minutes=30)

    @classmethod
    def start(
        cls,
        name: str,
        args: list[str] | None = None,
        group: str | None = None,
        duration: timezone.timedelta | None = None,
        user: User | None = None,
        allow_multiples: bool = False,
    ):
        if args is None:
            args = []
        try:
            with transaction.atomic():
                if not allow_multiples and Job.objects.filter(
                        name=name,
                        expected_termination__gte=timezone.now() - cls.TIMEOUT,
                        status=Job.Status.PENDING).exists():
                    return None
                if duration is None:
                    past_runs_duration: timezone.timedelta | None = Job.objects \
                        .filter(name=name, group=group, status=Job.Status.SUCCESS) \
                        .order_by('-created')[:5] \
                        .annotate(duration=models.F('termination') - models.F('created')) \
                        .aggregate(average_duration=models.Avg('duration'))['average_duration']
                    if past_runs_duration is None:
                        duration = timezone.timedelta(minutes=1)
                    else:
                        duration = past_runs_duration * 1.2
                return Job.objects.create(
                    name=name,
                    args=args,
                    group=group,
                    expected_termination=timezone.now() + duration,
                    started_by=user,
                    version=settings.VERSION,
                )
        except OperationalError as e:
            logging.exception(e, stack_info=True)
            return None

    @classmethod
    def get_or_start(cls, id: int | None, name: str, args: list[str] | None = None, group: str | None = None, duration: timezone.timedelta | None = None):
        if id is not None:
            try:
                return Job.objects.get(id=id)
            except Job.DoesNotExist:
                return None
        return cls.start(name=name, args=args, group=group, duration=duration)

    class Meta:
        verbose_name = 'job'
        verbose_name_plural = 'jobs'
        default_manager_name = 'objects'
        ordering = ['-created', 'name']
        indexes = [
            models.Index(fields=['name'], name='job_name_index')
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(expected_termination__gte=models.F('created')), name='job_expected_termination_gte_created')
        ]

    def __str__(self):
        return self.name
