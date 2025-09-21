from django.contrib.admin import TabularInline
from django.db.models import TextField, CharField
from django.forms import TextInput, Textarea
from adminsortable2.admin import SortableTabularInline
from django.http import HttpRequest
from spellbook.models import ZoneLocation, FeatureOfCard
from .utils import SpellbookAdminForm


def _textarea():
    return Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})


class IngredientInCombinationForm(SpellbookAdminForm):
    def clean(self):
        if 'zone_locations' in self.cleaned_data:
            locations = self.cleaned_data['zone_locations']
            if ZoneLocation.BATTLEFIELD not in locations:
                self.cleaned_data['battlefield_card_state'] = ''
            if ZoneLocation.EXILE not in locations:
                self.cleaned_data['exile_card_state'] = ''
            if ZoneLocation.GRAVEYARD not in locations:
                self.cleaned_data['graveyard_card_state'] = ''
            if ZoneLocation.LIBRARY not in locations:
                self.cleaned_data['library_card_state'] = ''
        return super().clean()

    class Meta:
        widgets = {
            'battlefield_card_state': _textarea(),
            'exile_card_state': _textarea(),
            'graveyard_card_state': _textarea(),
            'library_card_state': _textarea(),
        }


class IngredientAdmin(TabularInline):
    form = IngredientInCombinationForm
    extra = 0
    classes = ['ingredient']
    fields = [
        'quantity',
        'zone_locations',
        'battlefield_card_state',
        'exile_card_state',
        'graveyard_card_state',
        'library_card_state',
        'must_be_commander',
    ]


class FeatureOfCardAdmin(IngredientAdmin):
    related_field: str
    fields = [
        'attributes',
        IngredientAdmin.fields[0],
        'mana_needed',
        *IngredientAdmin.fields[1:],
        'easy_prerequisites',
        'notable_prerequisites',
    ]
    model = FeatureOfCard
    autocomplete_fields = ['attributes']
    formfield_overrides = {
        CharField: {'widget': TextInput(attrs={'size': '12'})},
        TextField: {'widget': _textarea()},
    }

    def get_fields(self, request: HttpRequest, obj: FeatureOfCard | None = None):
        return [self.related_field, *self.fields]

    def get_autocomplete_fields(self, request: HttpRequest):
        return [self.related_field, *self.autocomplete_fields]


class IngredientInCombinationAdmin(IngredientAdmin, SortableTabularInline):
    pass
