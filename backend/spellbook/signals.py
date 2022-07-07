import logging
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .variants import check_combo_sanity, check_feature_sanity
from .models import Combo
from django.db import IntegrityError


@receiver(m2m_changed, sender=Combo.needs.through)
@receiver(m2m_changed, sender=Combo.produces.through)
def combo_sanity_checker(sender, instance, action, reverse, model, **kwargs):
    if action == 'post_add':
        if reverse and not check_feature_sanity(instance):
            msg = f'Feature {instance.id} woul cause a recursion chain.'
            logging.error(msg)
            raise IntegrityError(msg)
        elif not reverse and not check_combo_sanity(instance):
            msg = f'Combo {instance.id} would cause a recursion chain.'
            logging.error(msg)
            raise IntegrityError(msg)
