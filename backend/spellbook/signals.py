from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Combo, Variant, CardInVariant, TemplateInVariant, CardInCombo, TemplateInCombo
from itertools import chain


@receiver(post_save, sender=Combo)
def update_new_variants(sender, instance: Combo, created, raw, **kwargs):
    if not raw and not created:
        for variant in instance.variants.filter(status__in=[Variant.Status.NEW, Variant.Status.RESTORE]):
            combos = variant.includes.all()
            for combo in chain(combos, variant.of.all()):
                for card in combo.uses.all():
                    civ = CardInVariant.objects.get(variant=variant, card=card)
                    cic = CardInCombo.objects.get(combo=combo, card=card)
                    civ.zone_location = cic.zone_location
                    civ.card_state = cic.card_state
                    civ.save()
                for template in combo.requires.all():
                    tiv = TemplateInVariant.objects.get(variant=variant, template=template)
                    tic = TemplateInCombo.objects.get(combo=combo, template=template)
                    tiv.zone_location = tic.zone_location
                    tiv.card_state = tic.card_state
                    tiv.save()
            variant.other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
            variant.mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
            variant.description = '\n'.join(c.description for c in combos if len(c.description) > 0)
            variant.status = Variant.Status.NEW
            variant.save()
