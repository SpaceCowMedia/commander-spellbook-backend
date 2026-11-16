from decimal import Decimal
from functools import cache
from django.db import models
from django.db.models.functions import Length
from constants import SORTED_COLORS


class Playable(models.Model):
    @classmethod
    @cache
    def playable_fields(cls):
        return ['identity', 'color', 'spoiler', 'mana_value'] + cls.legalities_fields() + cls.prices_fields()
    identity = models.CharField(max_length=5, blank=False, null=False, default='C', verbose_name='color identity', choices=[(c, c) for c in SORTED_COLORS.values()])
    color = models.CharField(max_length=5, blank=False, null=False, default='C', verbose_name='colors', choices=[(c, c) for c in SORTED_COLORS.values()])
    spoiler = models.BooleanField(default=False, help_text='Is this from an upcoming set?', verbose_name='is spoiler')
    mana_value = models.PositiveSmallIntegerField(default=0)
    identity_count = models.GeneratedField(
        db_persist=True,
        expression=models.Case(models.When(identity='C', then=models.Value(0)), default=Length('identity')),
        output_field=models.PositiveSmallIntegerField(default=0, verbose_name='identity color count'),
    )
    color_count = models.GeneratedField(
        db_persist=True,
        expression=models.Case(models.When(color='C', then=models.Value(0)), default=Length('color')),
        output_field=models.PositiveSmallIntegerField(default=0, verbose_name='color count'),
    )

    # Legalities
    @classmethod
    @cache
    def legalities_fields(cls):
        return [field for field in dir(cls) if field.startswith('legal_')]
    legal_commander = models.BooleanField(default=True, verbose_name='is legal in Commander')
    legal_pauper_commander_main = models.BooleanField(default=True, verbose_name='is legal in Pauper Commander main deck')
    legal_pauper_commander = models.BooleanField(default=True, verbose_name='is legal in Pauper Commander')
    legal_oathbreaker = models.BooleanField(default=True, verbose_name='is legal in Oathbreaker')
    legal_predh = models.BooleanField(default=True, verbose_name='is legal in Pre-Modern Commander')
    legal_standard_brawl = models.BooleanField(default=True, verbose_name='is legal in Standard Brawl')
    legal_brawl = models.BooleanField(default=True, verbose_name='is legal in Brawl')
    legal_competitive_brawl = models.BooleanField(default=True, verbose_name='is legal in Competitive Brawl')
    legal_alchemy = models.BooleanField(default=True, verbose_name='is legal in Alchemy')
    legal_vintage = models.BooleanField(default=True, verbose_name='is legal in Vintage')
    legal_legacy = models.BooleanField(default=True, verbose_name='is legal in Legacy')
    legal_premodern = models.BooleanField(default=True, verbose_name='is legal in PreModern')
    legal_modern = models.BooleanField(default=True, verbose_name='is legal in Modern')
    legal_pioneer = models.BooleanField(default=True, verbose_name='is legal in Pioneer')
    legal_standard = models.BooleanField(default=True, verbose_name='is legal in Standard')
    legal_pauper = models.BooleanField(default=True, verbose_name='is legal in Pauper')

    # Prices
    @classmethod
    @cache
    def prices_fields(cls):
        return [field for field in dir(cls) if field.startswith('price_')]
    price_tcgplayer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), verbose_name='TCGPlayer price (USD)')
    price_cardkingdom = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), verbose_name='Card Kingdom price (USD)')
    price_cardmarket = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), verbose_name='Cardmarket price (EUR)')

    class Meta:
        abstract = True
