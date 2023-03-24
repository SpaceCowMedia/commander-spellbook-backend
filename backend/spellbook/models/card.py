from urllib.parse import urlencode
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from .mixins import ScryfallLinkMixin
from .feature import Feature
from ..variants.list_utils import merge_identities
from .validators import IDENTITY_VALIDATORS


class Card(models.Model, ScryfallLinkMixin):
    name = models.CharField(max_length=255, unique=True, blank=False, help_text='Card name', verbose_name='name of card')
    oracle_id = models.UUIDField(unique=True, blank=True, null=True, help_text='Scryfall Oracle ID', verbose_name='Scryfall Oracle ID of card')
    features = models.ManyToManyField(
        to=Feature,
        related_name='cards',
        help_text='Features provided by this single card effects or characteristics',
        blank=True)
    identity = models.CharField(max_length=5, blank=False, null=False, default='C', help_text='Card mana identity', verbose_name='mana identity of card', validators=IDENTITY_VALIDATORS)
    legal = models.BooleanField(default=True, help_text='Is this card legal in Commander?', verbose_name='is legal')
    spoiler = models.BooleanField(default=False, help_text='Is this card from an upcoming set?', verbose_name='is spoiler')
    added = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ['name']
        verbose_name = 'card'
        verbose_name_plural = 'cards'

    def __str__(self):
        return self.name

    def query_string(self):
        return urlencode({'q': f'!"{self.name}"'})


@receiver(post_save, sender=Card, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance, created, raw, **kwargs):
    from .variant import Variant
    if raw:
        return
    if created:
        return
    variants_to_save = []
    for variant in instance.used_in_variants.all():
        save = False
        if variant.legal and not instance.legal:
            variant.legal = False
            save = True
        elif not variant.legal and instance.legal:
            variant.legal = all(card.legal for card in variant.uses.all())
            save = True
        if not variant.spoiler and instance.spoiler:
            variant.spoiler = True
            save = True
        elif variant.spoiler and not instance.spoiler:
            variant.spoiler = any(card.spoiler for card in variant.uses.all())
            save = True
        if instance.identity != variant.identity:
            variant.identity = merge_identities(card.identity for card in variant.uses.all())
            save = True
        if save:
            variants_to_save.append(variant)
    Variant.objects.bulk_update(variants_to_save, ['legal', 'spoiler', 'identity'])
