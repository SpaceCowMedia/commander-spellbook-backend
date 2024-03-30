from decimal import Decimal
from django.db import models
from django.db.models.functions import Length
from django.db.models.fields.generated import GeneratedField
from .utils import SORTED_COLORS


class Playable(models.Model):
    @classmethod
    def playable_fields(cls):
        return ['identity', 'spoiler'] + cls.legalities_fields() + cls.prices_fields()
    identity = models.CharField(max_length=5, blank=False, null=False, default='C', verbose_name='color identity', choices=[(c, c) for c in SORTED_COLORS.values()])
    spoiler = models.BooleanField(default=False, help_text='Is this from an upcoming set?', verbose_name='is spoiler')
    identity_count = GeneratedField(
        db_persist=True,
        expression=models.Case(models.When(identity='C', then=models.Value(0)), default=Length('identity')),
        output_field=models.PositiveSmallIntegerField(default=0, verbose_name='identity color count'),
    )

    # Legalities
    @classmethod
    def legalities_fields(cls):
        return [field.name for field in cls._meta.get_fields() if field.name.startswith('legal_')]
    legal_commander = models.BooleanField(default=True, help_text='Is this legal in Commander?', verbose_name='is legal in Commander')
    legal_pauper_commander_main = models.BooleanField(default=True, help_text='Is this legal in Pauper Commander main deck?', verbose_name='is legal in Pauper Commander main deck')
    legal_pauper_commander = models.BooleanField(default=True, help_text='Is this legal in Pauper Commander?', verbose_name='is legal in Pauper Commander')
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
