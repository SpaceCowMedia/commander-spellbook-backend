from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Combo, Variant
from .variants.variants_generator import restore_variant
from .variants.variant_data import RestoreData


@receiver(post_save, sender=Combo)
def update_new_variants(sender, instance: Combo, created, raw, **kwargs):
    if not raw and not created:
        for variant in list[Variant](instance.variants.filter(status__in=[Variant.Status.NEW, Variant.Status.RESTORE])):
            uses_set, requires_set = restore_variant(
                variant,
                list(variant.includes.all()),
                list(variant.of.all()),
                list(variant.uses_set.all()),
                list(variant.requires_set.all()),
                data=RestoreData())
            variant.save()
            for uses in uses_set:
                uses.save()
            for requires in requires_set:
                requires.save()
