from decimal import Decimal
from django.db import models


class Playable(models.Model):
    # Legalities
    @classmethod
    def legalities_fields(cls):
        return [field.name for field in cls._meta.get_fields() if field.name.startswith('legal_')]
    legal_commander = models.BooleanField(default=True, help_text='Is this card legal in Commander?', verbose_name='is legal in Commander')
    legal_pauper_commander_main = models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander main deck?', verbose_name='is legal in Pauper Commander main deck')
    legal_pauper_commander_commander = models.BooleanField(default=True, help_text='Is this card legal in Pauper Commander as commander?', verbose_name='is legal in Pauper Commander as commander')
    legal_oathbreaker = models.BooleanField(default=True, help_text='Is this card legal in Oathbreaker?', verbose_name='is legal in Oathbreaker')
    legal_predh = models.BooleanField(default=True, help_text='Is this card legal in PreDH Commander?', verbose_name='is legal in Pre-Modern Commander')
    legal_brawl = models.BooleanField(default=True, help_text='Is this card legal in Brawl?', verbose_name='is legal in Brawl')
    legal_vintage = models.BooleanField(default=True, help_text='Is this card legal in Vintage?', verbose_name='is legal in Vintage')
    legal_legacy = models.BooleanField(default=True, help_text='Is this card legal in Legacy?', verbose_name='is legal in Legacy')
    legal_modern = models.BooleanField(default=True, help_text='Is this card legal in Modern?', verbose_name='is legal in Modern')
    legal_pioneer = models.BooleanField(default=True, help_text='Is this card legal in Pioneer?', verbose_name='is legal in Pioneer')
    legal_standard = models.BooleanField(default=True, help_text='Is this card legal in Standard?', verbose_name='is legal in Standard')
    legal_pauper = models.BooleanField(default=True, help_text='Is this card legal in Pauper?', verbose_name='is legal in Pauper')

    # Prices
    @classmethod
    def prices_fields(cls):
        return [field.name for field in cls._meta.get_fields() if field.name.startswith('price_')]
    price_tcgplayer = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Card price on TCGPlayer', verbose_name='TCGPlayer price (USD)')
    price_cardkingdom = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Card price on Card Kingdom', verbose_name='Card Kingdom price (USD)')
    price_cardmarket = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal(0), help_text='Card price on Cardmarket', verbose_name='Cardmarket price (EUR)')

    class Meta:
        abstract = True
