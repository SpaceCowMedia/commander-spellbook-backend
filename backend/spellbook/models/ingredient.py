from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.forms import MultipleChoiceField, ValidationError as FormValidationError, CheckboxSelectMultiple
from .validators import TEXT_VALIDATORS
from .constants import MAX_LOCATION_STATE_LENGTH


class CheckboxSelectMultipleAsCharField(CheckboxSelectMultiple):
    def format_value(self, value):
        if value is not None and isinstance(value, str):
            value = list(value)
        return super().format_value(value)


class MultipleChoiceFieldAsCharField(MultipleChoiceField):
    def __init__(self, *args, **kwargs):
        kwargs.pop('max_length', None)
        kwargs['widget'] = CheckboxSelectMultipleAsCharField
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        return ''.join(super().to_python(value))  # type: ignore

    def validate(self, value):
        super().validate(value)
        if len(value) > len(self.choices):  # type: ignore
            raise FormValidationError('Too many choices.')


class ZoneLocation(models.TextChoices):
    HAND = 'H'
    BATTLEFIELD = 'B'
    COMMAND_ZONE = 'C'
    EXILE = 'E'
    GRAVEYARD = 'G'
    LIBRARY = 'L'


class ZoneLocationsField(models.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('help_text', 'Starting location(s) for the card.')
        kwargs.setdefault('verbose_name', 'starting location')
        kwargs['max_length'] = len(ZoneLocation.choices)
        super().__init__(*args, **kwargs)

    def formfield(self, **kwargs):
        kwargs['form_class'] = MultipleChoiceFieldAsCharField
        kwargs['choices'] = ZoneLocation.choices
        return super().formfield(**kwargs)


class Ingredient(models.Model):
    quantity = models.PositiveSmallIntegerField(default=1, blank=False, help_text='Quantity of the card in the combo.', verbose_name='quantity', validators=[MinValueValidator(1)])
    zone_locations = ZoneLocationsField(blank=False)
    battlefield_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card on the battlefield, if present.', validators=TEXT_VALIDATORS, verbose_name='battlefield starting card state')
    exile_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in exile, if present.', validators=TEXT_VALIDATORS, verbose_name='exile starting card state')
    graveyard_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in the graveyard, if present.', validators=TEXT_VALIDATORS, verbose_name='graveyard starting card state')
    library_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in the library, if present.', validators=TEXT_VALIDATORS, verbose_name='library starting card state')
    must_be_commander = models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')

    def clean(self):
        self.clean_data(vars(self))

    @classmethod
    def clean_data(cls, data: dict):
        zone_locations = data.get('zone_locations')
        if zone_locations is None:
            return
        must_be_commander = data.get('must_be_commander', False)
        if zone_locations == ZoneLocation.COMMAND_ZONE and not must_be_commander:
            raise ValidationError('Any card that can only start in command zone must be a commander. Please check the "must be commander" checkbox.')
        if ZoneLocation.BATTLEFIELD not in zone_locations and data.get('battlefield_card_state'):
            raise ValidationError('Battlefield card state is only valid if the card starts on the battlefield.')
        if ZoneLocation.EXILE not in zone_locations and data.get('exile_card_state'):
            raise ValidationError('Exile card state is only valid if the card starts in exile.')
        if ZoneLocation.GRAVEYARD not in zone_locations and data.get('graveyard_card_state'):
            raise ValidationError('Graveyard card state is only valid if the card starts in the graveyard.')
        if ZoneLocation.LIBRARY not in zone_locations and data.get('library_card_state'):
            raise ValidationError('Library card state is only valid if the card starts in the library.')

    class Meta:
        abstract = True
        ordering = ['id']


class IngredientInCombination(Ingredient):
    order = models.PositiveIntegerField(default=0, db_index=True, blank=False, help_text='Order of the card in the combo.', verbose_name='order')

    class Meta(Ingredient.Meta):
        abstract = True
        ordering = ['order', 'id']
