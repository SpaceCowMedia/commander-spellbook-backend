from django.forms import ModelForm, MultipleChoiceField, ValidationError, CheckboxSelectMultiple, Textarea
from django.contrib import admin
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


def _textarea():
    return Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})


class IngredientInCombinationForm(ModelForm):
    zone_locations = MultipleChoiceFieldAsCharField(choices=IngredientInCombination.ZoneLocation.choices, required=True)

    def clean(self):
        key = 'ingredient_count'
        if key in self.cleaned_data:
            self.cleaned_data[key] += 1
        else:
            self.cleaned_data[key] = 1
        self.instance.order = self.cleaned_data[key]

        if 'zone_locations' in self.cleaned_data:
            locations = self.cleaned_data['zone_locations']
            if IngredientInCombination.ZoneLocation.BATTLEFIELD not in locations:
                self.cleaned_data['battlefield_card_state'] = ''
            if IngredientInCombination.ZoneLocation.EXILE not in locations:
                self.cleaned_data['exile_card_state'] = ''
            if IngredientInCombination.ZoneLocation.GRAVEYARD not in locations:
                self.cleaned_data['graveyard_card_state'] = ''
            if IngredientInCombination.ZoneLocation.LIBRARY not in locations:
                self.cleaned_data['library_card_state'] = ''
        return super().clean()

    class Meta:
        widgets = {
            'battlefield_card_state': _textarea(),
            'exile_card_state': _textarea(),
            'graveyard_card_state': _textarea(),
            'library_card_state': _textarea(),
        }


class IngredientAdmin(admin.TabularInline):
    form = IngredientInCombinationForm
    extra = 0
    classes = ['ingredient']
    fields = ['quantity', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state', 'must_be_commander']
