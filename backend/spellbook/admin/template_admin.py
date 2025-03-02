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
        replacement_forms: str = self.data.get('templatereplacement_set-TOTAL_FORMS', '0')
        if cleaned_data.get('scryfall_query'):
            if replacement_forms.isdigit():
                replacement_form_count = int(replacement_forms)
                if replacement_form_count > 0 and not all(self.data.get(f'templatereplacement_set-{i}-DELETE', 'off') == 'on' for i in range(replacement_form_count)):
                    self.add_error('scryfall_query', 'Cannot have both a Scryfall query and replacements')
        elif replacement_forms == '0':
            self.add_error('scryfall_query', 'Must have either a Scryfall query or replacements')
        return cleaned_data


@admin.register(Template)
class TemplateAdmin(SpellbookModelAdmin):
    form = TemplateAdminForm
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fields = ['name', 'id', 'updated', 'created', 'scryfall_query', 'scryfall_link', 'description']
    list_display = ['name', 'id', 'scryfall_query', 'updated']
    search_fields = [
        '=pk',
        'name',
        'scryfall_query',
    ]
    inlines = [TemplateReplacementAdminInline]
