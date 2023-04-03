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
    card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in its starting location.', validators=TEXT_VALIDATORS, verbose_name='starting card state')

    class Meta:
        abstract = True
        ordering = ['order', 'id']
