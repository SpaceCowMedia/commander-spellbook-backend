from django.db import models
from django.core.exceptions import ValidationError
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
    must_be_commander = models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')

    def clean(self) -> None:
        if self.zone_locations == IngredientInCombination.ZoneLocation.COMMAND_ZONE and not self.must_be_commander:
            raise ValidationError('Any card that can only start in command zone must be a commander. Please check the "must be commander" checkbox.')
        if IngredientInCombination.ZoneLocation.BATTLEFIELD not in self.zone_locations and self.battlefield_card_state:
            raise ValidationError('Battlefield card state is only valid if the card starts on the battlefield.')
        if IngredientInCombination.ZoneLocation.EXILE not in self.zone_locations and self.exile_card_state:
            raise ValidationError('Exile card state is only valid if the card starts in exile.')
        if IngredientInCombination.ZoneLocation.LIBRARY not in self.zone_locations and self.library_card_state:
            raise ValidationError('Library card state is only valid if the card starts in the library.')
        if IngredientInCombination.ZoneLocation.GRAVEYARD not in self.zone_locations and self.graveyard_card_state:
            raise ValidationError('Graveyard card state is only valid if the card starts in the graveyard.')

    class Meta:
        abstract = True
        ordering = ['order', 'id']
