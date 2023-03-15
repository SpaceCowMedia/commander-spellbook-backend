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
