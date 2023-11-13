from django.contrib import admin
from spellbook.models.template import Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fields = ['name', 'scryfall_query', 'scryfall_link']
    list_display = ['name', 'id', 'scryfall_query']
    search_fields = ['name', 'scryfall_query']
