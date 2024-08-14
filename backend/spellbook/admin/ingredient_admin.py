from django.forms import Textarea
from django.contrib.admin import TabularInline
from adminsortable2.admin import SortableTabularInline
from spellbook.models import ZoneLocation
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
    fields = ['quantity', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state', 'must_be_commander']


class IngredientInCombinationAdmin(IngredientAdmin, SortableTabularInline):
    template = 'adminsortable2/edit_inline/tabular-django-5.0.html'  # TODO: remove when https://github.com/jrief/django-admin-sortable2/issues/405 is fixed
    pass
