from django.contrib import admin
from spellbook.models import Card
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
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']

    def get_readonly_fields(self, request, obj):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.oracle_id is not None:
            return readonly_fields \
                + ['name', 'oracle_id', 'identity', 'spoiler'] \
                + Card.legalities_fields() \
                + Card.prices_fields()
        return readonly_fields

    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return False
        return super().has_delete_permission(request, obj) and not obj.used_in_combos.exists() and not obj.used_in_variants.exists()
