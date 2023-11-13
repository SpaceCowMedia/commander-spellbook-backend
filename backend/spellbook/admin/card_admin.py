from typing import Any
from django.contrib import admin
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.http.request import HttpRequest
from spellbook.models import Card, Variant
from .utils import IdentityFilter


class ManagedByScryfallFilter(admin.SimpleListFilter):
    title = 'managed by Scryfall'
    parameter_name = 'has_oracle_id'

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def queryset(self, request, queryset):
        if self.value() == 'True':
            return queryset.exclude(oracle_id__isnull=True)
        elif self.value() == 'False':
            return queryset.filter(oracle_id__isnull=True)


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fieldsets = [
        ('Spellbook', {'fields': [
            'name',
            'features'
        ]}),
        ('Scryfall', {
            'fields': [
                'scryfall_link',
                'oracle_id',
                'type_line',
                'oracle_text',
                'identity',
                'spoiler'
            ],
            'description': 'Scryfall data is updated periodically.'
        }),
        ('Legalities', {
            'fields': Card.legalities_fields(),
            'classes': ['collapse'],
            'description': 'Legalities are updated periodically rom Scryfall.'
        }),
        ('Prices', {
            'fields': Card.prices_fields(),
            'classes': ['collapse'],
            'description': 'Prices are updated periodically from EDHREC.'
        }),
    ]
    # inlines = [FeatureInline]
    list_filter = [IdentityFilter, 'legal_commander', ManagedByScryfallFilter]
    search_fields = ['name', 'features__name', 'type_line', 'oracle_text']
    autocomplete_fields = ['features']
    list_display = ['name', 'id', 'identity', 'variants_count']

    def get_readonly_fields(self, request, obj):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.oracle_id is not None:
            return readonly_fields \
                + ['scryfall_link', 'oracle_id', 'type_line', 'oracle_text', 'identity', 'spoiler'] \
                + Card.legalities_fields() \
                + Card.prices_fields()
        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return super().has_delete_permission(request, obj) and not obj.used_in_combos.exists() and not obj.used_in_variants.exists()

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request) \
            .annotate(variants_count=Count('used_in_variants', distinct=True, filter=Q(used_in_variants__status__in=Variant.public_statuses())))

    @admin.display(ordering='variants_count')
    def variants_count(self, obj: Any) -> int:
        return obj.variants_count
