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

    def get_readonly_fields(self, request, obj):
        readonly_fields = super().get_readonly_fields(request, obj)
        if obj is not None and obj.oracle_id is not None:
            return readonly_fields + ['name', 'oracle_id', 'identity', 'legal', 'spoiler']
        return readonly_fields
