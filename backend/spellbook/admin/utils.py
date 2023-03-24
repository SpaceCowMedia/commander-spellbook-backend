from itertools import combinations
from django.contrib import admin
from django.utils.html import format_html
from django.utils.formats import localize


def datetime_to_html(datetime):
    if datetime is None:
        return None
    return format_html('<span class="local-datetime" data-iso="{}">{}</span>', datetime.isoformat(), localize(datetime))


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
        return [(i, i) for i in (''.join(t) or 'C' for l in range(6) for t in combinations('WUBRG', l))]

    def queryset(self, request, queryset):
        if self.value() is not None:
            return queryset.filter(identity=self.value())
        return queryset
