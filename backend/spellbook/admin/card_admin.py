from django.contrib import admin, messages
from django.db.models import Q
from django.http.request import HttpRequest
from django.shortcuts import redirect
from django.urls import path
from spellbook.models import Card, CardType
from .utils import IdentityFilter, SpellbookModelAdmin, CustomFilter
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

    def curate_card(self, request: HttpRequest, object_id: str):
        card = Card.objects.filter(pk=object_id).first()
        if not card:
            messages.error(request, f'Card with id {object_id} does not exist.')
            return redirect('admin:spellbook_card_changelist')
        if request.method == 'POST' and self.has_change_permission(request, card):
            if card.number is None:
                card.ensure_number()
                messages.success(request, f'Curated {card.name} as card number {card.number}.')
            else:
                messages.warning(request, f'{card.name} is already curated as card number {card.number}.')
        return redirect('admin:spellbook_card_change', object_id)

    def get_urls(self):
        return [
            path(
                '<path:object_id>/curate/',
                self.admin_site.admin_view(view=self.curate_card, cacheable=False),
                name='spellbook_card_curate',
            ),
            *super().get_urls(),
        ]

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        if obj.number is None:
            return super().has_delete_permission(request, obj)
        return super().has_delete_permission(request, obj) and not obj.used_in_combos.exists() and not obj.used_in_variants.exists()
