from django.db import models


class Feature(models.Model):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature')
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    utility = models.BooleanField(default=False, help_text='Is this a utility feature? Utility features are hidden to the end users', verbose_name='is utility')

    class Meta:
        ordering = ['name']
        verbose_name = 'feature'
        verbose_name_plural = 'features'

    def __str__(self):
        return self.name
