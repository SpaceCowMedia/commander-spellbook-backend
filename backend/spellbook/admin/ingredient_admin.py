from django.contrib.admin import TabularInline
from django.db.models import TextField, CharField
from django.forms import TextInput, Textarea
from adminsortable2.admin import SortableTabularInline
from django.http import HttpRequest
from spellbook.models import FeatureOfCard, Ingredient
from spellbook.models.fields import DictionaryField
from .utils import DictionaryWidget, SpellbookAdminForm


def _textarea():
    return Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})


class IngredientForm(SpellbookAdminForm):
    def clean(self):
        if 'zone_locations' in self.cleaned_data:
            locations = self.cleaned_data['zone_locations']
            for location, state in Ingredient.CARD_STATE_FIELDS.items():
                if location not in locations:
                    self.cleaned_data[state] = ''
        return super().clean()

    class Meta:
        widgets = {state: _textarea() for state in Ingredient.CARD_STATE_FIELDS.values()}


class IngredientAdmin(TabularInline):
    form = IngredientForm
    extra = 0
    classes = ['ingredient']
    formfield_overrides = {
        DictionaryField: {'widget': DictionaryWidget},
    }
    fields = [
        'quantity',
        'zone_locations',
        *Ingredient.CARD_STATE_FIELDS.values(),
        'must_be_commander',
    ]


class FeatureOfCardAdmin(IngredientAdmin):
    related_field: str
    fields = [
        'attributes',
        IngredientAdmin.fields[0],  # pyright: ignore[reportGeneralTypeIssues]
        'used_face',
        *IngredientAdmin.fields[1:],
        'dictionary',
    ]
    model = FeatureOfCard
    autocomplete_fields = ['attributes']
    formfield_overrides = {
        **IngredientAdmin.formfield_overrides,
        CharField: {'widget': TextInput(attrs={'size': '12'})},
        TextField: {'widget': _textarea()},
    }

    def get_fields(self, request: HttpRequest, obj: FeatureOfCard | None = None):
        return [self.related_field, *self.fields]

    def get_autocomplete_fields(self, request: HttpRequest):
        return [self.related_field, *self.autocomplete_fields]


class OrderedIngredientAdmin(IngredientAdmin, SortableTabularInline):
    pass


class ComboIngredientAdmin(OrderedIngredientAdmin):
    fields = [*OrderedIngredientAdmin.fields, 'dictionary']
