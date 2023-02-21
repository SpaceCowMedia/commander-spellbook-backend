from django.contrib import admin
from ..models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {
            'fields': ['scryfall_link', 'oracle_id', 'identity', 'legal'],
            'description': 'Scryfall data should be consistent with what Scryfall says about this card. Editors must take care to ensure that the data is correct.'}),
    ]
    # inlines = [FeatureInline]
    list_filter = ['identity', 'legal']
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']
