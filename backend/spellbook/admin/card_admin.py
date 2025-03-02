from django.contrib import admin
from django.db.models import Q, TextField
from django.forms.widgets import Textarea
from spellbook.models import Card, FeatureOfCard, CardType
from .utils import IdentityFilter, SpellbookModelAdmin, CustomFilter
from .ingredient_admin import IngredientAdmin


class ManagedByScryfallFilter(CustomFilter):
    title = 'managed by Scryfall'
    parameter_name = 'has_oracle_id'
    data_type = bool

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def filter(self, value: data_type) -> Q:
        return Q(oracle_id__isnull=not value)


class CardTypeFilter(CustomFilter):
    title = 'type'
    parameter_name = 'type'
    data_type = str

    def lookups(self, request, model_admin):
        return CardType.choices

    def filter(self, value: data_type) -> Q:
        return Q(type_line__icontains=value)


class FeatureOfCardAdminInline(IngredientAdmin):
    fields = ['feature', *IngredientAdmin.fields, 'easy_prerequisites', 'notable_prerequisites', 'attributes']
    model = FeatureOfCard
    verbose_name = 'Feature'
    verbose_name_plural = 'Features'
    autocomplete_fields = ['feature', 'attributes']
    formfield_overrides = {
        TextField: {'widget': Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})},
    }


@admin.register(Card)
class CardAdmin(SpellbookModelAdmin):
    readonly_fields = ['id', 'scryfall_link']
    scryfall_fields = ['oracle_id'] + Card.scryfall_fields()
    fieldsets = [
        ('Spellbook', {'fields': [
            'name',
            'id',
        ]}),
        ('Scryfall', {
            'fields': [
                'scryfall_link',
                *scryfall_fields,
            ],
            'description': 'Scryfall data is updated periodically.'
        }),
        ('Legalities', {
            'fields': Card.legalities_fields(),
            'classes': ['collapse'],
            'description': 'Legalities are updated periodically from Scryfall.'
        }),
        ('Prices', {
            'fields': Card.prices_fields(),
            'classes': ['collapse'],
            'description': 'Prices are updated periodically from EDHREC.'
        }),
    ]
    list_filter = [
        IdentityFilter,
        CardTypeFilter,
        'legal_commander',
        ManagedByScryfallFilter,
        'game_changer',
        'tutor',
        'mass_land_denial',
        'extra_turn',
    ]
    search_fields = [
        '=pk',
        'name',
        'name_unaccented',
        'name_unaccented_simplified',
        'name_unaccented_simplified_with_spaces',
    ]
    autocomplete_fields = ['features']
    list_display = ['name', 'id', 'identity', 'variant_count']
    inlines = [FeatureOfCardAdminInline]

    def lookup_allowed(self, lookup: str, value: str) -> bool:
        if lookup in (
            'replaces__id',
        ):
            return False
        return super().lookup_allowed(lookup, value)

    def get_readonly_fields(self, request, obj):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.oracle_id is not None:
            return readonly_fields \
                + self.scryfall_fields \
                + Card.legalities_fields() \
                + Card.prices_fields()
        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return super().has_delete_permission(request, obj) and not obj.used_in_combos.exists() and not obj.used_in_variants.exists()
