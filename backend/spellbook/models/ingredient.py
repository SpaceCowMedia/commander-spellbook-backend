from django.db import models
from django.db.models import Index
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms import MultipleChoiceField, ValidationError as FormValidationError, CheckboxSelectMultiple
from .validators import TEXT_VALIDATORS
from .constants import MAX_LOCATION_STATE_LENGTH, MAX_INGREDIENT_QUANTITY
from .utils import case_insensitive_trigram_indexes


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
    CARD_STATE_FIELDS = {
        ZoneLocation.BATTLEFIELD: 'battlefield_card_state',
        ZoneLocation.EXILE: 'exile_card_state',
        ZoneLocation.GRAVEYARD: 'graveyard_card_state',
        ZoneLocation.LIBRARY: 'library_card_state',
    }
    CARD_STATE_ZONE_NAMES = {
        ZoneLocation.BATTLEFIELD: 'on the battlefield',
        ZoneLocation.EXILE: 'in exile',
        ZoneLocation.GRAVEYARD: 'in the graveyard',
        ZoneLocation.LIBRARY: 'in the library',
    }

    quantity = models.PositiveSmallIntegerField(default=1, blank=False, help_text='Quantity of the card in the combo.', verbose_name='quantity', validators=[MinValueValidator(1), MaxValueValidator(MAX_INGREDIENT_QUANTITY)])
    zone_locations = ZoneLocationsField(blank=False)
    battlefield_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card on the battlefield, if present.', validators=TEXT_VALIDATORS, verbose_name='battlefield starting card state')
    exile_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in exile, if present.', validators=TEXT_VALIDATORS, verbose_name='exile starting card state')
    graveyard_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in the graveyard, if present.', validators=TEXT_VALIDATORS, verbose_name='graveyard starting card state')
    library_card_state = models.CharField(max_length=MAX_LOCATION_STATE_LENGTH, blank=True, help_text='State of the card in the library, if present.', validators=TEXT_VALIDATORS, verbose_name='library starting card state')
    must_be_commander = models.BooleanField(default=False, help_text='Does the card have to be a commander?', verbose_name='must be commander')

    @classmethod
    def text_fields_with_references(cls) -> list[str]:
        return list(cls.CARD_STATE_FIELDS.values())

    @classmethod
    def card_state_trigram_indexes(cls, prefix: str) -> list[Index]:
        return case_insensitive_trigram_indexes(prefix, **{field: field.removesuffix('_card_state') for field in cls.CARD_STATE_FIELDS.values()})

    def clean(self):
        super().clean()
        self.clean_data(vars(self))

    @classmethod
    def clean_data(cls, data: dict):
        zone_locations = data.get('zone_locations')
        if zone_locations is None:
            return
        must_be_commander = data.get('must_be_commander', False)
        if zone_locations == ZoneLocation.COMMAND_ZONE and not must_be_commander:
            raise ValidationError('Any card that can only start in command zone must be a commander. Please check the "must be commander" checkbox.')
        for location, state in cls.CARD_STATE_FIELDS.items():
            if location not in zone_locations and data.get(state):
                raise ValidationError(f'{location.label} card state is only valid if the card starts {cls.CARD_STATE_ZONE_NAMES[location]}.')

    class Meta:
        abstract = True
        ordering = ['id']


class OrderedIngredient(Ingredient):
    order = models.PositiveIntegerField(default=0, db_index=True, blank=False, help_text='Order of the card in the combo.', verbose_name='order')

    class Meta(Ingredient.Meta):
        abstract = True
        ordering = ['order', 'id']


class ComboIngredient(OrderedIngredient):
    in_text_substitutions = models.BooleanField(default=True, help_text='Does this ingredient appear in the text that replaces the features this combo produces?', verbose_name='in text substitutions')

    class Meta(OrderedIngredient.Meta):
        abstract = True
