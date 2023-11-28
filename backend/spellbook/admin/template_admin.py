from django.contrib import admin
from spellbook.models.template import Template
from .utils import SpellbookModelAdmin


@admin.register(Template)
class TemplateAdmin(SpellbookModelAdmin):
    readonly_fields = ['scryfall_link']
    fields = ['name', 'scryfall_query', 'scryfall_link']
    list_display = ['name', 'id', 'scryfall_query']
    search_fields = ['name', 'scryfall_query']
