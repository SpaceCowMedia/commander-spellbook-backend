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
        ANY = 'A'
    order = models.IntegerField(blank=False, help_text='Order of the card in the combo.', verbose_name='order')
    zone_location = models.CharField(choices=ZoneLocation.choices, default=ZoneLocation.HAND, max_length=2, blank=False, help_text='Starting location for the card.', verbose_name='starting location')
    card_state = models.CharField(max_length=200, blank=True, default='', help_text='State of the card in its starting location.', validators=TEXT_VALIDATORS, verbose_name='starting card state')

    class Meta:
        abstract = True
        ordering = ['order', 'id']
