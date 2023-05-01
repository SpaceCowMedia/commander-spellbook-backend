from django.template import loader
from rest_framework import filters
from rest_framework.compat import coreapi, coreschema
from django.utils.encoding import force_str
from spellbook.parsers import variants_query_parser, NotSupportedError


class SpellbookQueryFilter(filters.BaseFilterBackend):
    search_param = 'q'
    template = 'rest_framework/filters/search.html'
    search_title = 'Search'
    search_description = 'A search query.'

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
            queryset = variants_query_parser(queryset, search_terms)
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

    def get_schema_fields(self, view):
        assert coreapi is not None, 'coreapi must be installed to use `get_schema_fields()`'
        assert coreschema is not None, 'coreschema must be installed to use `get_schema_fields()`'
        return [
            coreapi.Field(
                name=self.search_param,
                required=False,
                location='query',
                schema=coreschema.String(
                    title=force_str(self.search_title),
                    description=force_str(self.search_description)
                )
            )
        ]

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
