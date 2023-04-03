from django.forms import ModelForm, MultipleChoiceField, ValidationError, CheckboxSelectMultiple
from spellbook.models import IngredientInCombination


class CheckboxSelectMultipleAsCharField(CheckboxSelectMultiple):
    def format_value(self, value):
        if value is not None and isinstance(value, str):
            value = list(value)
        return super().format_value(value)


class MultipleChoiceFieldAsCharField(MultipleChoiceField):
    widget = CheckboxSelectMultipleAsCharField

    def to_python(self, value):
        return ''.join(super().to_python(value))

    def validate(self, value):
        super().validate(value)
        if len(value) > len(self.choices):
            raise ValidationError('Too many choices.')


class IngredientInCombinationForm(ModelForm):
    zone_locations = MultipleChoiceFieldAsCharField(choices=IngredientInCombination.ZoneLocation.choices, required=True)
