import logging
from django.utils import timezone
from django.db import models, transaction, OperationalError
from django.contrib.auth.models import User


class Job(models.Model):
    class Status(models.TextChoices):
        SUCCESS = 'S'
        FAILURE = 'F'
        PENDING = 'P'
    name = models.CharField(max_length=255, blank=False, verbose_name='name of job')
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
        help_text='User that started this job')

    @classmethod
    def start(cls, name: str, duration: timezone.timedelta | None = None, user: User | None = None):
        try:
            with transaction.atomic():
                if Job.objects.filter(
                        name=name,
                        expected_termination__gte=timezone.now(),
                        status=Job.Status.PENDING).exists():
                    return None
                if duration is None:
                    past_runs_duration: timezone.timedelta = Job.objects \
                        .filter(name=name, status=Job.Status.SUCCESS) \
                        .order_by('-created')[:5] \
                        .annotate(duration=models.F('termination') - models.F('created')) \
                        .aggregate(average_duration=models.Avg('duration'))['average_duration']
                    if past_runs_duration is None:
                        duration = timezone.timedelta(minutes=1)
                    else:
                        duration = past_runs_duration * 1.2
                return Job.objects.create(
                    name=name,
                    expected_termination=timezone.now() + duration,
                    started_by=user)
        except OperationalError as e:
            logging.exception(e, stack_info=True)
            return None

    @classmethod
    def get_or_start(cls, name: str, id: int | None = None, duration: timezone.timedelta | None = None):
        if id is not None:
            try:
                return Job.objects.get(id=id)
            except Job.DoesNotExist:
                return None
        return cls.start(name=name, duration=duration)

    class Meta:
        verbose_name = 'job'
        verbose_name_plural = 'jobs'
        default_manager_name = 'objects'
        ordering = ['-created', 'name']
        indexes = [
            models.Index(fields=['name'], name='job_name_index')
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(expected_termination__gte=models.F('created')), name='job_expected_termination_gte_created')
        ]

    def __str__(self):
        return self.name
