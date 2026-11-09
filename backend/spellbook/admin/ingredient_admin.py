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


class DictionaryAdminInline(TabularInline):
    '''An inline whose rows hold a dictionary: its fields, then the dictionary, edited in a dialog of its own.'''
    formfield_overrides = {
        DictionaryField: {'widget': DictionaryWidget},
    }

    def get_fields(self, request: HttpRequest, obj=None):
        return [*(self.fields or ()), 'dictionary']


class WithFeatureAttributesAdminInline(DictionaryAdminInline):
    '''An inline of the rows producing a feature: the related object, the attributes the feature is
    produced with, its fields, then what the row provides for the feature.'''
    related_field: str

    def get_fields(self, request: HttpRequest, obj=None):
        return [self.related_field, 'attributes', *super().get_fields(request, obj)]

    def get_autocomplete_fields(self, request: HttpRequest):
        return [self.related_field, 'attributes', *super().get_autocomplete_fields(request)]


class IngredientAdmin(TabularInline):
    form = IngredientForm
    extra = 0
    classes = ['ingredient']
    fields = [
        'quantity',
        'zone_locations',
        *Ingredient.CARD_STATE_FIELDS.values(),
        'must_be_commander',
    ]


class FeatureOfCardAdmin(WithFeatureAttributesAdminInline, IngredientAdmin):
    fields = [
        IngredientAdmin.fields[0],  # pyright: ignore[reportGeneralTypeIssues]
        'used_face',
        *IngredientAdmin.fields[1:],
        'is_mana_needed_an_accurate_minimum',
    ]
    model = FeatureOfCard
    formfield_overrides = {
        **WithFeatureAttributesAdminInline.formfield_overrides,
        CharField: {'widget': TextInput(attrs={'size': '12'})},
        TextField: {'widget': _textarea()},
    }


class OrderedIngredientAdmin(IngredientAdmin, SortableTabularInline):
    pass


class ComboIngredientAdmin(OrderedIngredientAdmin, DictionaryAdminInline):
    '''Sortable first, so that its order field comes after the dictionary.'''
