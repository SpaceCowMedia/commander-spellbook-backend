from typing import Any
from django.contrib import admin
from spellbook.models.template import Template, TemplateReplacement
from .utils import SpellbookAdminForm, SpellbookModelAdmin


class TemplateReplacementAdminInline(admin.StackedInline):
    model = TemplateReplacement
    extra = 0
    autocomplete_fields = ['card']
    verbose_name = 'Replacement'
    verbose_name_plural = 'Replacements'


class TemplateAdminForm(SpellbookAdminForm):
    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data.get('scryfall_query') and cleaned_data.get('template_replacements-TOTAL_FORMS') != '0':
            self.add_error('scryfall_query', 'Cannot have both a Scryfall query and replacements')
        return cleaned_data


@admin.register(Template)
class TemplateAdmin(SpellbookModelAdmin):
    form = TemplateAdminForm
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fields = ['name', 'id', 'updated', 'created', 'scryfall_query', 'scryfall_link', 'description']
    list_display = ['name', 'id', 'scryfall_query', 'updated']
    search_fields = ['name', 'scryfall_query']
    inlines = [TemplateReplacementAdminInline]
