from django.db import models
from django.db.models.functions import Lower
from django.contrib.postgres.indexes import GinIndex
from .validators import NAME_VALIDATORS


class Feature(models.Model):
    MAX_FEATURE_NAME_LENGTH = 255
    name = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature', validators=NAME_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    utility = models.BooleanField(default=False, help_text='Is this a utility feature? Utility features are hidden to the end users', verbose_name='is utility')

    class Meta:
        ordering = ['name']
        verbose_name = 'feature'
        verbose_name_plural = 'features'
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='name_unique_ci',
                violation_error_message='Feature name should be unique, ignoring case.',
            ),
        ]
        indexes = [
            GinIndex(fields=['name']),
        ]

    def __str__(self):
        return self.name
