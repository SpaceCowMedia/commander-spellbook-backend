from django.contrib import admin, messages
from django.contrib.admin import ActionLocation, action
from django.db.models import Q, QuerySet
from django.http.request import HttpRequest
from spellbook.models import Card, CardType
from .utils import IdentityFilter, SpellbookModelAdmin, CustomFilter, join_for_message, object_tool
from .ingredient_admin import FeatureOfCardAdmin


class ManagedByScryfallFilter(CustomFilter):
    title = 'managed by Scryfall'
    parameter_name = 'has_oracle_id'
    data_type = bool

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def filter(self, value: bool) -> Q:
        return Q(oracle_id__isnull=not value)


class CuratedFilter(CustomFilter):
    title = 'curated'
    parameter_name = 'curated'
    data_type = bool

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def filter(self, value: bool) -> Q:
        return Q(number__isnull=not value)


class CardTypeFilter(CustomFilter):
    title = 'type'
    parameter_name = 'type'
    data_type = str

    def lookups(self, request, model_admin):
        return CardType.choices

    def filter(self, value: str) -> Q:
        return Q(type_line__icontains=value)


class FeatureOfCardAdminInline(FeatureOfCardAdmin):
    related_field = 'feature'
    verbose_name = 'Feature'
    verbose_name_plural = 'Features'


@admin.register(Card)
class CardAdmin(SpellbookModelAdmin):
    actions = ['curate']
    readonly_fields = ['number', 'scryfall_link', 'power_value', 'toughness_value', 'loyalty_value']
    scryfall_fields = ['oracle_id'] + Card.scryfall_fields()
    fieldsets = [  # pyright: ignore[reportAssignmentType]
        ('Spellbook', {'fields': [
            'name',
            'number',
        ]}),
        ('Scryfall', {
            'fields': [
                'scryfall_link',
                *scryfall_fields,
            ],
            'description': 'Scryfall data is updated periodically.',
            'classes': ['collapse'],
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
        CuratedFilter,
        CardTypeFilter,
        'legal_commander',
        ManagedByScryfallFilter,
        'game_changer',
        'tutor',
        'mass_land_denial',
        'extra_turn',
    ]
    search_fields = [
        '=number',
        'name',
        'name_unaccented',
        'name_unaccented_simplified',
        'name_unaccented_simplified_with_spaces',
    ]
    autocomplete_fields = ['features']
    list_display = ['name', 'number', 'identity', 'variant_count']
    inlines = [FeatureOfCardAdminInline]

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'replaces__id',
        ):
            return False
        return super().lookup_allowed(lookup, value, request)  # type: ignore  # deprecated typing

    def get_readonly_fields(self, request, obj):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.oracle_id is not None:
            return readonly_fields \
                + self.scryfall_fields \
                + Card.legalities_fields() \
                + Card.prices_fields()
        return readonly_fields

    @object_tool(shown_for=lambda card: card.number is None)
    @action(description='Curate this card, so that combos and templates can use it', description_plural='Curate selected cards, so that combos and templates can use them', permissions=['change'], location=[ActionLocation.CHANGE_FORM, ActionLocation.CHANGE_LIST])  # type: ignore[call-overload]
    def curate(self, request: HttpRequest, queryset: QuerySet[Card]) -> None:
        curated: list[Card] = []
        already_curated: list[Card] = []
        for card in queryset.order_by('name'):
            if card.number is None:
                card.ensure_number()
                curated.append(card)
            else:
                already_curated.append(card)
        if curated:
            messages.success(request, f'Curated {join_for_message(f"{card.name} as card number {card.number}" for card in curated)}.')
        if already_curated:
            messages.warning(request, f'Already curated: {join_for_message(f"{card.name} as card number {card.number}" for card in already_curated)}.')

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        if obj.number is None:
            return super().has_delete_permission(request, obj)
        return super().has_delete_permission(request, obj) and not obj.used_in_combos.exists() and not obj.used_in_variants.exists()
