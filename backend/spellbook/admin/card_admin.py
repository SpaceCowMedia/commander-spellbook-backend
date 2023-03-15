from django.contrib import admin
from ..models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {
            'fields': ['scryfall_link', 'oracle_id', 'identity', 'legal', 'spoiler'],
            'description': 'Scryfall data is updated periodically.'}),
    ]
    # inlines = [FeatureInline]
    list_filter = ['identity', 'legal']
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']

    def has_change_permission(self, request, obj: Card | None = None) -> bool:
        return obj is not None and obj.oracle_id is None and super().has_change_permission(request, obj)
