from django.db import models
from django.db.models.functions import Lower
from .validators import FIRST_CAPITAL_LETTER_VALIDATOR, TEXT_VALIDATORS


class Feature(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature', validators=[FIRST_CAPITAL_LETTER_VALIDATOR, *TEXT_VALIDATORS])
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

    def __str__(self):
        return self.name
