from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.functions import Lower
from django.contrib.postgres.indexes import GinIndex
from .constants import MAX_FEATURE_NAME_LENGTH
from .validators import NAME_VALIDATORS


class Feature(models.Model):
    name = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature', validators=NAME_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of a produced effect', verbose_name='description of the feature')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    utility = models.BooleanField(default=False, help_text='Is this a utility feature? Utility features are hidden to the end users', verbose_name='is utility')

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
            GinIndex(fields=['name']),
        ]

    def __str__(self):
        return self.name


@receiver(post_save, sender=Feature, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance, created, raw, **kwargs):
    from .variant import Variant
    if raw or created:
        return
    variants = Variant.recipes_prefetched.filter(produces=instance)
    variants_to_save = []
    for variant in variants:
        new_variant_name = variant._str()
        if new_variant_name != variant.name:
            variant.name = new_variant_name
            variants_to_save.append(variant)
    Variant.objects.bulk_update(variants_to_save, ['name'])


@receiver(post_save, sender=Feature, dispatch_uid='update_combo_fields')
def update_combo_fields(sender, instance, created, raw, **kwargs):
    from .combo import Combo
    if raw or created:
        return
    combos = Combo.objects.filter(models.Q(produces=instance) | models.Q(needs=instance))
    combos_to_save = []
    for combo in combos:
        new_combo_name = combo._str()
        if new_combo_name != combo.name:
            combo.name = new_combo_name
            combos_to_save.append(combo)
    Combo.objects.bulk_update(combos_to_save, ['name'])
