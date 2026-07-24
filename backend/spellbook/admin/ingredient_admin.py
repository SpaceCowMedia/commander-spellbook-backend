from django.contrib.admin import TabularInline
from django.db.models import TextField, CharField
from django.forms import TextInput, Textarea
from adminsortable2.admin import SortableTabularInline
from django.http import HttpRequest
from spellbook.models import ZoneLocation, FeatureOfCard, Card
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
        'used_face',
        'attributes',
        IngredientAdmin.fields[0],  # pyright: ignore[reportGeneralTypeIssues]
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

    def get_fields(self, request: HttpRequest, obj: FeatureOfCard | Card | None = None):
        fields = [self.related_field, *self.fields]
        # On a card's change page the parent object is the Card itself: hide the used-face
        # selector for cards that are not multi-faced, since it would never be applicable.
        if isinstance(obj, Card) and obj.faces <= 1 and 'used_face' in fields:
            fields.remove('used_face')
        return fields

    def get_autocomplete_fields(self, request: HttpRequest):
        return [self.related_field, *self.autocomplete_fields]


class IngredientInCombinationAdmin(IngredientAdmin, SortableTabularInline):
    pass
