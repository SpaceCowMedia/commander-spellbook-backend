import re
from itertools import combinations
from typing import Any
from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize
from django.utils.text import normalize_newlines
from django.forms import CharField, Textarea, ModelForm
from spellbook.models.validators import ORACLE_SYMBOL


def datetime_to_html(datetime):
    if datetime is None:
        return None
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


def upper_oracle_symbols(text: str):
    return re.sub(r'\{' + ORACLE_SYMBOL + r'\}', lambda m: m.group(0).upper(), text, flags=re.IGNORECASE)


class NormalizedTextField(CharField):
    widget = Textarea

    def to_python(self, value: Any):
        value = super().to_python(value)
        return normalize_newlines(value)


class ComboVariantForm(ModelForm):
    def clean_mana_needed(self):
        if self.cleaned_data['mana_needed']:
            result = upper_oracle_symbols(self.cleaned_data['mana_needed'])
            return result
        return self.cleaned_data['mana_needed']

    class Meta:
        field_classes = {
            'other_prerequisites': NormalizedTextField,
            'description': NormalizedTextField,
        }


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
