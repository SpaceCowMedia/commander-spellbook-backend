from django.db import models, connection
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.functions import Lower, Upper
from django.contrib.postgres.indexes import GinIndex, OpClass
from .utils import batch_size_or_default
from .constants import MAX_FEATURE_NAME_LENGTH
from .validators import NAME_VALIDATORS


class Feature(models.Model):
    class Status(models.TextChoices):
        HIDDEN_UTILITY = 'HU'
        PUBLIC_UTILITY = 'PU'
        HELPER = 'H'
        CONTEXTUAL = 'C'
        STANDALONE = 'S'

    id: int
    name = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, unique=True, blank=False, help_text='Short name for a produced effect', verbose_name='name of feature', validators=NAME_VALIDATORS)
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
        ] + ([
            GinIndex(OpClass(Upper('name'), name='gin_trgm_ops'), name='feature_name_trgm_idx'),
        ] if connection.vendor == 'postgresql' else [])

    def __str__(self):
        return self.name


@receiver(post_save, sender=Feature, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance, created, raw, **kwargs):
    if raw or created:
        return
    from .variant import Variant
    variants_query = Variant.recipes_prefetched.filter(produces=instance)
    variant_count = variants_query.count()
    batch_size = batch_size_or_default(variant_count)
    for i in range(0, variant_count, batch_size):
        variants_to_save = []
        variants = list[Variant](variants_query[i:i + batch_size])
        for variant in variants:
            new_variant_name = variant._str()
            if new_variant_name != variant.name:
                variant.name = new_variant_name
                variants_to_save.append(variant)
        Variant.objects.bulk_update(variants_to_save, ['name'])


@receiver(post_save, sender=Feature, dispatch_uid='update_combo_fields')
def update_combo_fields(sender, instance, created, raw, **kwargs):
    if raw or created:
        return
    from .combo import Combo
    combos = Combo.recipes_prefetched.filter(models.Q(produces=instance) | models.Q(needs=instance))
    combo_count = combos.count()
    batch_size = batch_size_or_default(combo_count)
    for i in range(0, combo_count, batch_size):
        combos_to_save = []
        batch_combos = list[Combo](combos[i:i + batch_size])
        for combo in batch_combos:
            new_combo_name = combo._str()
            if new_combo_name != combo.name:
                combo.name = new_combo_name
                combos_to_save.append(combo)
        Combo.objects.bulk_update(combos_to_save, ['name'])
