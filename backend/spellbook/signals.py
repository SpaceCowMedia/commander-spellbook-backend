import logging
import traceback
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Combo, Variant

@receiver(post_save, sender=Combo)
def update_new_variants(sender, instance: Combo, created, raw, **kwargs):
    if not raw and not created:
        for variant in instance.variants.filter(status__in=[Variant.Status.NEW, Variant.Status.RESTORE]):
            combos = variant.includes.all()
            variant.zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
            variant.cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
            variant.other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
            variant.mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
            variant.description = '\n'.join(c.description for c in combos if len(c.description) > 0)
            variant.status = Variant.Status.NEW
            variant.save()
