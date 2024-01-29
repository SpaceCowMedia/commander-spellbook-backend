import re
from itertools import combinations
from datetime import datetime
from typing import Any
from django.db.models import TextField, Count, Q
from django.contrib import admin
from django.db.models.query import QuerySet
from django.utils.html import format_html
from django.utils.formats import localize
from django.forms import Textarea
from django.contrib.admin import ModelAdmin
from spellbook.models.validators import ORACLE_SYMBOL
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes


def datetime_to_html(datetime: datetime) -> str | None:
    if datetime is None:
        return None
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


def upper_oracle_symbols(text: str):
    return re.sub(r'\{' + ORACLE_SYMBOL + r'\}', lambda m: m.group(0).upper(), text, flags=re.IGNORECASE)


def auto_fix_missing_braces_to_oracle_symbols(text: str):
    if re.compile(r'^' + ORACLE_SYMBOL + r'+$').match(text):
        return re.sub(r'\{?(' + ORACLE_SYMBOL + r')\}?', r'{\1}', text, flags=re.IGNORECASE)
    return text


class NormalizedTextareaWidget(Textarea):
    def value_from_datadict(self, data, files, name: str):
        s = super().value_from_datadict(data, files, name)
        return sanitize_newlines_apostrophes_and_quotes(s)


class SpellbookModelAdmin(ModelAdmin):
    formfield_overrides = {
        TextField: {'widget': NormalizedTextareaWidget},
    }

    def get_form(self, request, obj, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)

        def clean_mana_needed(self):
            if self.cleaned_data['mana_needed']:
                result = auto_fix_missing_braces_to_oracle_symbols(self.cleaned_data['mana_needed'])
                result = upper_oracle_symbols(result)
                return result
            return self.cleaned_data['mana_needed']
        form.clean_mana_needed = clean_mana_needed
        return form

    def get_search_results(self, request, queryset, search_term: str):
        result = queryset
        may_have_duplicates = False
        split_by_or = search_term.replace(' + ', ' ').split(' | ')
        if len(split_by_or) > 1:
            first = True
            for sub_term in split_by_or:
                sub_term = sub_term.strip()
                if sub_term:
                    partial_result, d = super().get_search_results(request, queryset, sub_term)
                    may_have_duplicates |= d
                    if first:
                        first = False
                        result = partial_result
                    else:
                        result = result | partial_result
        else:
            split_by_and = search_term.split(' + ')
            for sub_term in split_by_and:
                sub_term = sub_term.strip()
                if sub_term:
                    result, d = super().get_search_results(request, result, sub_term)
                    may_have_duplicates |= d
        return result, may_have_duplicates


class CustomFilter(admin.SimpleListFilter):
    data_type = str

    def queryset(self, request: Any, queryset: QuerySet[Any]) -> QuerySet[Any] | None:
        value = self.value()
        allowed_values = {str(lookup) for lookup, _ in self.lookup_choices}
        if value is None or value not in allowed_values:
            return queryset
        return queryset.filter(self.filter(self.data_type(value))).distinct()

    def filter(self, value: data_type) -> Q:
        raise NotImplementedError()

    def get_facet_counts(self, pk_attname, filtered_qs):
        counts = {}
        for i, choice in enumerate(self.lookup_choices):
            counts[f"{i}__c"] = Count(
                pk_attname,
                filter=self.filter(choice[0])
            )
        return counts


class IdentityFilter(CustomFilter):
    title = 'identity'
    parameter_name = 'identity'

    def lookups(self, request, model_admin):
        return [(i, i) for i in (''.join(t) or 'C' for length in range(6) for t in combinations('WUBRG', length))]

    def filter(self, value: str) -> Q:
        return Q(identity=value)


class CardsCountListFilter(CustomFilter):
    title = 'cards count'
    parameter_name = 'cards_count'
    one_more_than_max = DEFAULT_CARD_LIMIT + 1
    one_more_than_max_display = f'{one_more_than_max}+'

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(2, CardsCountListFilter.one_more_than_max)] + [(CardsCountListFilter.one_more_than_max_display, CardsCountListFilter.one_more_than_max_display)]

    def filter(self, value: str) -> Q:
        match value:
            case CardsCountListFilter.one_more_than_max_display:
                return Q(cards_count__gte=CardsCountListFilter.one_more_than_max)
            case _:
                return Q(cards_count=int(value))
