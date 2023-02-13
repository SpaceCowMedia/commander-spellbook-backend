from django.contrib import admin
from ..models import Template


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fields = ['name', 'scryfall_query', 'scryfall_link']
    list_display = ['name', 'scryfall_query', 'id']
    search_fields = ['name', 'scryfall_query']
