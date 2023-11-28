import re
from itertools import combinations
from typing import Any
from datetime import datetime
from django.db.models import TextField, DateTimeField
from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize
from django.utils.safestring import SafeText
from django.utils.text import normalize_newlines
from django.forms import Textarea
from django.forms.widgets import DateTimeInput
from django.contrib.admin import ModelAdmin
from spellbook.models.validators import ORACLE_SYMBOL


def datetime_to_html(datetime: datetime) -> str | None:
    if datetime is None:
        return None
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


def upper_oracle_symbols(text: str):
    return re.sub(r'\{' + ORACLE_SYMBOL + r'\}', lambda m: m.group(0).upper(), text, flags=re.IGNORECASE)


class NormalizedTextareaWidget(Textarea):
    def value_from_datadict(self, data, files, name: str):
        return normalize_newlines(super().value_from_datadict(data, files, name))


class SpellbookModelAdmin(ModelAdmin):
    formfield_overrides = {
        TextField: {'widget': NormalizedTextareaWidget},
    }

    def get_form(self, request, obj, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        def clean_mana_needed(self):
            if self.cleaned_data['mana_needed']:
                result = upper_oracle_symbols(self.cleaned_data['mana_needed'])
                return result
            return self.cleaned_data['mana_needed']
        form.clean_mana_needed = clean_mana_needed
        return form


class SearchMultipleRelatedMixin:
    def get_search_results(self, request, queryset, search_term: str):
        result = queryset
        may_have_duplicates = False
        for sub_term in search_term.split(' + '):
            sub_term = sub_term.strip()
            if sub_term:
                result, d = super().get_search_results(request, result, sub_term)
                may_have_duplicates |= d
        return result, may_have_duplicates


class IdentityFilter(admin.SimpleListFilter):
    title = 'identity'
    parameter_name = 'identity'

    def lookups(self, request, model_admin):
        return [(i, i) for i in (''.join(t) or 'C' for length in range(6) for t in combinations('WUBRG', length))]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(identity=self.value())
        return queryset
