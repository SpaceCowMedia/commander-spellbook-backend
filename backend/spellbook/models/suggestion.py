from django.db import models
from django.contrib.auth.models import User
from .validators import TEXT_VALIDATORS


class Suggestion(models.Model):
    class Status(models.TextChoices):
        NEW = 'N'
        AWAITING_DISCUSSION = 'AD'
        PENDING_APPROVAL = 'PA'
        ACCEPTED = 'A'
        REJECTED = 'R'

    id: int
    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Suggestion status for editors', max_length=2)
    comment = models.TextField(blank=True, max_length=2**10, help_text='Comment written by the user that suggested this', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='User that suggested this', related_name='%(class)s')

    class Meta:
        abstract = True
        default_manager_name = 'objects'
        ordering = [
            models.Case(
                *(models.When(status=s, then=models.Value(i)) for i, s in enumerate(('N', 'PA', 'AD', 'A', 'R'))),
                default=models.Value(10),
            ),
            'created',
        ]
