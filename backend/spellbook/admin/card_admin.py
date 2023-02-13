from django.contrib import admin
from ..models import Card


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {'fields': ['oracle_id', 'identity', 'legal']}),
    ]
    # inlines = [FeatureInline]
    list_filter = ['identity', 'legal']
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']
