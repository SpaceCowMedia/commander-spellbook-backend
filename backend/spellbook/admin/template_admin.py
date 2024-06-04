from django.contrib import admin
from spellbook.models.template import Template
from .utils import SpellbookModelAdmin


@admin.register(Template)
class TemplateAdmin(SpellbookModelAdmin):
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fields = ['name', 'id', 'updated', 'created', 'scryfall_query', 'scryfall_link', 'description']
    list_display = ['name', 'id', 'scryfall_query', 'updated']
    search_fields = ['name', 'scryfall_query']
