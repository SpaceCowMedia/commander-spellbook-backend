from typing import Iterable
from decimal import Decimal
from django.db import models
from .validators import IDENTITY_VALIDATORS
from .utils import merge_identities


class Playable(models.Model):
    @classmethod
    def playable_fields(cls):
        return ['identity', 'spoiler'] + cls.legalities_fields() + cls.prices_fields()
    identity = models.CharField(max_length=5, blank=False, null=False, default='C', help_text='mana identity', verbose_name='mana identity', validators=IDENTITY_VALIDATORS)
    spoiler = models.BooleanField(default=False, help_text='Is this from an upcoming set?', verbose_name='is spoiler')

    # Legalities
    @classmethod
    def legalities_fields(cls):
        return [field.name for field in cls._meta.get_fields() if field.name.startswith('legal_')]
    legal_commander = models.BooleanField(default=True, help_text='Is this legal in Commander?', verbose_name='is legal in Commander')
    legal_pauper_commander_main = models.BooleanField(default=True, help_text='Is this legal in Pauper Commander main deck?', verbose_name='is legal in Pauper Commander main deck')
    legal_pauper_commander_commander = models.BooleanField(default=True, help_text='Is this legal in Pauper Commander as commander?', verbose_name='is legal in Pauper Commander as commander')
    legal_oathbreaker = models.BooleanField(default=True, help_text='Is this legal in Oathbreaker?', verbose_name='is legal in Oathbreaker')
    legal_predh = models.BooleanField(default=True, help_text='Is this legal in PreDH Commander?', verbose_name='is legal in Pre-Modern Commander')
    legal_brawl = models.BooleanField(default=True, help_text='Is this legal in Brawl?', verbose_name='is legal in Brawl')
    legal_vintage = models.BooleanField(default=True, help_text='Is this legal in Vintage?', verbose_name='is legal in Vintage')
    legal_legacy = models.BooleanField(default=True, help_text='Is this legal in Legacy?', verbose_name='is legal in Legacy')
    legal_modern = models.BooleanField(default=True, help_text='Is this legal in Modern?', verbose_name='is legal in Modern')
    legal_pioneer = models.BooleanField(default=True, help_text='Is this legal in Pioneer?', verbose_name='is legal in Pioneer')
    legal_standard = models.BooleanField(default=True, help_text='Is this legal in Standard?', verbose_name='is legal in Standard')
    legal_pauper = models.BooleanField(default=True, help_text='Is this legal in Pauper?', verbose_name='is legal in Pauper')

    # Prices
    @classmethod
    def prices_fields(cls):
        return [field.name for field in cls._meta.get_fields() if field.name.startswith('price_')]
    price_tcgplayer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Price on TCGPlayer', verbose_name='TCGPlayer price (USD)')
    price_cardkingdom = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Price on Card Kingdom', verbose_name='Card Kingdom price (USD)')
    price_cardmarket = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Price on Cardmarket', verbose_name='Cardmarket price (EUR)')

    class Meta:
        abstract = True

    def update(self, playables: Iterable['Playable']) -> bool:
        '''Update this playable with the given playables. Return True if any field was changed, False otherwise.'''
        old_values = {field: getattr(self, field) for field in self.playable_fields()}
        self.identity = merge_identities(playable.identity for playable in playables)
        self.spoiler = any(playable.spoiler for playable in playables)
        self.legal_commander = all(playable.legal_commander for playable in playables)
        self.legal_pauper_commander_main = all(playable.legal_pauper_commander_main for playable in playables)
        self.legal_pauper_commander_commander = all(playable.legal_pauper_commander_commander for playable in playables)
        self.legal_oathbreaker = all(playable.legal_oathbreaker for playable in playables)
        self.legal_predh = all(playable.legal_predh for playable in playables)
        self.legal_brawl = all(playable.legal_brawl for playable in playables)
        self.legal_vintage = all(playable.legal_vintage for playable in playables)
        self.legal_legacy = all(playable.legal_legacy for playable in playables)
        self.legal_modern = all(playable.legal_modern for playable in playables)
        self.legal_pioneer = all(playable.legal_pioneer for playable in playables)
        self.legal_standard = all(playable.legal_standard for playable in playables)
        self.legal_pauper = all(playable.legal_pauper for playable in playables)
        self.price_tcgplayer = sum(playable.price_tcgplayer for playable in playables)
        self.price_cardkingdom = sum(playable.price_cardkingdom for playable in playables)
        self.price_cardmarket = sum(playable.price_cardmarket for playable in playables)
        new_values = {field: getattr(self, field) for field in self.playable_fields()}
        return old_values != new_values
