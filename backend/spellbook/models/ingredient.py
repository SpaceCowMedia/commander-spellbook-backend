from django.db import models
from .validators import TEXT_VALIDATORS


class IngredientInCombination(models.Model):
    class ZoneLocation(models.TextChoices):
        HAND = 'H'
        BATTLEFIELD = 'B'
        COMMAND_ZONE = 'C'
        GRAVEYARD = 'G'
        LIBRARY = 'L'
        EXILE = 'E'
    order = models.IntegerField(blank=False, help_text='Order of the card in the combo.', verbose_name='order')
    zone_locations = models.CharField(default=ZoneLocation.HAND, max_length=len(ZoneLocation.choices), blank=False, help_text='Starting location(s) for the card.', verbose_name='starting location')
    battlefield_card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card on the battlefield, if present.', validators=TEXT_VALIDATORS, verbose_name='battlefield starting card state')
    exile_card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in exile, if present.', validators=TEXT_VALIDATORS, verbose_name='exile starting card state')
    library_card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in the library, if present.', validators=TEXT_VALIDATORS, verbose_name='library starting card state')
    graveyard_card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in the graveyard, if present.', validators=TEXT_VALIDATORS, verbose_name='graveyard starting card state')

    class Meta:
        abstract = True
        ordering = ['order', 'id']
