from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.functions import Lower
from .constants import MAX_FEATURE_NAME_LENGTH
from .mixins import NamedModel
from .utils import case_insensitive_trigram_indexes
from .validators import NAME_VALIDATORS


class Feature(NamedModel):
    class Status(models.TextChoices):
        HIDDEN_UTILITY = 'HU'
        PUBLIC_UTILITY = 'PU'
        HELPER = 'H'
        CONTEXTUAL = 'C'
        STANDALONE = 'S'

    id: int
    name = NamedModel.name_field(max_length=MAX_FEATURE_NAME_LENGTH, help_text='Short name for a produced effect', verbose_name='name of feature', validators=NAME_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of the feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    status = models.CharField(choices=Status.choices, default=Status.HIDDEN_UTILITY, help_text='Is this feature an utility for variant generation, a helper to be exploited somehow, or a standalone, probably impactful effect? (public utilities are visible to combo submitters)', verbose_name='status', max_length=2)
    uncountable = models.BooleanField(default=False, help_text='Is this an uncountable feature? Uncountable features can only appear in one copy and speed up variant generation.', verbose_name='is uncountable')

    @property
    def is_utility(self) -> bool:
        return self.status in (self.Status.HIDDEN_UTILITY, self.Status.PUBLIC_UTILITY)

    class Meta:
        verbose_name = 'feature'
        verbose_name_plural = 'features'
        default_manager_name = 'objects'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                Lower('name'),
                name='name_unique_ci',
                violation_error_message='Feature name should be unique, ignoring case.',
            ),
        ]
        indexes = [
            models.Index(fields=['status']),
        ] + case_insensitive_trigram_indexes('feature', 'name')

    def __str__(self):
        return self.name


@receiver(post_save, sender=Feature, dispatch_uid='update_feature_references')
def update_feature_references(sender, instance: Feature, created, raw, **kwargs):
    if raw or created or not instance.renamed_from:
        return
    from .references import replace_feature_references
    replace_feature_references(instance, instance.renamed_from)
