from django.db.models.signals import m2m_changed, post_delete
from django.dispatch import receiver
from .models import Card, Feature, Combo
from .variants import update_variants



# @receiver(m2m_changed, sender=Card.features.through)
# @receiver(m2m_changed, sender=Combo.includes.through)
# @receiver(m2m_changed, sender=Combo.needs.through)
# @receiver(m2m_changed, sender=Combo.produces.through)
# def on_many_to_many_update(sender, instance, action, reverse, model, **kwargs):
#     if action in ['post_clear']:
#         update_variants()

# @receiver(post_delete, sender=Card)
# @receiver(post_delete, sender=Feature)
# @receiver(post_delete, sender=Combo)
# def on_delete(sender, instance, **kwargs):
#     update_variants()
