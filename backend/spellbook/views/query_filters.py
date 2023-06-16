from django.db.models import QuerySet
from django.template import loader
from rest_framework import filters
from django.utils.encoding import force_str
from spellbook.parsers import variants_query_parser, NotSupportedError


class AbstractQueryFilter(filters.BaseFilterBackend):
    search_param = 'q'
    template = 'rest_framework/filters/search.html'
    search_title = 'Search'
    search_description = 'A search query.'

    def query_parser(self, queryset: QuerySet, search_terms: str):
        raise NotImplementedError

    def get_search_terms(self, request) -> str:
        """
        Search terms are set by a ?q=... query parameter,
        and may be whitespace delimited.
        """
        params = request.query_params.get(self.search_param, '')
        params = params.replace('\x00', '')  # strip null characters
        return params

    def filter_queryset(self, request, queryset, view):
        search_terms = self.get_search_terms(request)

        try:
            queryset = self.query_parser(queryset, search_terms)
            return queryset
        except NotSupportedError:
            return queryset.none()

    def to_html(self, request, queryset, view):
        term = self.get_search_terms(request)
        term = term if term else ''
        context = {
            'param': self.search_param,
            'term': term
        }
        template = loader.get_template(self.template)
        return template.render(context)

    def get_schema_operation_parameters(self, view):
        return [
            {
                'name': self.search_param,
                'required': False,
                'in': 'query',
                'description': force_str(self.search_description),
                'schema': {
                    'type': 'string',
                },
            },
        ]


class SpellbookQueryFilter(AbstractQueryFilter):
    def query_parser(self, queryset, search_terms):
        return variants_query_parser(queryset, search_terms)


class CardQueryFilter(AbstractQueryFilter):
    def query_parser(self, queryset, search_terms):
        if search_terms == '?':
            return queryset.order_by('?')
        return queryset.filter(name__icontains=search_terms)
