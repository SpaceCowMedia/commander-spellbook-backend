from django.db.models import QuerySet, Case, Value, When, Q, F
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
        params = params.replace('\x00', '')  # remove null characters
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


class AutocompleteQueryFilter(AbstractQueryFilter):
    fields = []

    def query_parser(self, queryset, search_terms):
        if search_terms == '?':
            return queryset.order_by('?')
        annotations = {}
        filters = Q()
        for field in self.fields:
            filters |= Q(**{f'{field}__icontains': search_terms})
            annotations[f'{field}_match_score'] = Case(
                When(**{f'{field}__iexact': search_terms}, then=Value(0)),
                When(**{f'{field}__istartswith': search_terms}, then=Value(1)),
                default=Value(10),
            )
        order_by = [match_score for match_score in annotations.keys()] + [field for field in self.fields]
        return queryset.filter(filters).annotate(**annotations).order_by(*order_by)


class NameAutocompleteQueryFilter(AutocompleteQueryFilter):
    fields = ['name']


class NameAndDescriptionAutocompleteQueryFilter(AutocompleteQueryFilter):
    fields = ['name', 'description']


class NameAndScryfallAutocompleteQueryFilter(AutocompleteQueryFilter):
    fields = ['name', 'scryfall_query']


class OrderingFilterWithNullsLast(filters.OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            ordering_with_nulls = []
            for field in ordering:
                if '?' in field:
                    ordering_with_nulls.append(field)
                elif field.startswith('-'):
                    ordering_with_nulls.append(F(field[1:]).desc(nulls_last=True))
                else:
                    ordering_with_nulls.append(F(field).asc(nulls_last=True))
            return queryset.order_by(*ordering_with_nulls)

        return queryset
