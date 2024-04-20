from django.db import models
from django.core.exceptions import ValidationError
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH
from .validators import TEXT_VALIDATORS
from .utils import recipe


class Ingredient(models.Model):
    class ZoneLocation(models.TextChoices):
        HAND = 'H'
        BATTLEFIELD = 'B'
        COMMAND_ZONE = 'C'
        EXILE = 'E'
        GRAVEYARD = 'G'
        LIBRARY = 'L'

    zone_locations = models.CharField(default=ZoneLocation.HAND, max_length=len(ZoneLocation.choices), blank=False, help_text='Starting location(s) for the card.', verbose_name='starting location')
    battlefield_card_state = models.CharField(max_length=200, blank=True, help_text='State of the card on the battlefield, if present.', validators=TEXT_VALIDATORS, verbose_name='battlefield starting card state')
    exile_card_state = models.CharField(max_length=200, blank=True, help_text='State of the card in exile, if present.', validators=TEXT_VALIDATORS, verbose_name='exile starting card state')
    graveyard_card_state = models.CharField(max_length=200, blank=True, help_text='State of the card in the graveyard, if present.', validators=TEXT_VALIDATORS, verbose_name='graveyard starting card state')
    library_card_state = models.CharField(max_length=200, blank=True, help_text='State of the card in the library, if present.', validators=TEXT_VALIDATORS, verbose_name='library starting card state')
    must_be_commander = models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')

    def clean(self) -> None:
        self.clean_data(vars(self))

    @classmethod
    def clean_data(cls, data: dict) -> None:
        if data['zone_locations'] == IngredientInCombination.ZoneLocation.COMMAND_ZONE and not data['must_be_commander']:
            raise ValidationError('Any card that can only start in command zone must be a commander. Please check the "must be commander" checkbox.')
        if IngredientInCombination.ZoneLocation.BATTLEFIELD not in data['zone_locations'] and data['battlefield_card_state']:
            raise ValidationError('Battlefield card state is only valid if the card starts on the battlefield.')
        if IngredientInCombination.ZoneLocation.EXILE not in data['zone_locations'] and data['exile_card_state']:
            raise ValidationError('Exile card state is only valid if the card starts in exile.')
        if IngredientInCombination.ZoneLocation.GRAVEYARD not in data['zone_locations'] and data['graveyard_card_state']:
            raise ValidationError('Graveyard card state is only valid if the card starts in the graveyard.')
        if IngredientInCombination.ZoneLocation.LIBRARY not in data['zone_locations'] and data['library_card_state']:
            raise ValidationError('Library card state is only valid if the card starts in the library.')

    class Meta:
        abstract = True
        ordering = ['id']


class IngredientInCombination(Ingredient):
    order = models.PositiveIntegerField(blank=False, help_text='Order of the card in the combo.', verbose_name='order')

    class Meta(Ingredient.Meta):
        abstract = True
        ordering = ['order', 'id']


class Recipe(models.Model):
    name = models.CharField(max_length=MAX_CARD_NAME_LENGTH * 10 + MAX_FEATURE_NAME_LENGTH * 5 + 10, editable=False)

    def cards(self) -> list:
        return []

    def templates(self) -> list:
        return []

    def features_needed(self) -> list:
        return []

    def features_produced(self) -> list:
        return []

    def _str(self) -> str:
        if self.pk is None:
            base = f'New {self._meta.model_name}'
            if hasattr(self, 'id') and self.id is not None:  # type: ignore
                base += f' with unique id <{self.id}>'  # type: ignore
            return base
        return self.compute_name(self.cards(), self.templates(), self.features_needed(), self.features_produced())

    def __str__(self) -> str:
        if self.name:
            return self.name
        return self._str()

    @classmethod
    def compute_name(
        cls,
        cards: list,
        templates: list,
        features_needed: list,
        features_produced: list,
    ) -> str:
        return recipe(
            [str(card) for card in cards] + [str(feature) for feature in features_needed] + [str(template) for template in templates],
            [str(feature) for feature in features_produced][:4]
        )

    class Meta:
        abstract = True
