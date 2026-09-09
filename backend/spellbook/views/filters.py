from uuid import UUID
from django_filters.fields import ModelMultipleChoiceField
from django.db.models import QuerySet, Case, Value, When, Q, F
from django.core.exceptions import FieldDoesNotExist, ValidationError as DjangoValidationError
from django.template import loader
from django_filters.rest_framework import ModelMultipleChoiceFilter
from rest_framework import filters
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from django.utils.encoding import force_str
from spellbook.models import Card
from spellbook.transformers.variants_query_transformer import variants_query_parser

CARD_REFERENCE_HELP = 'The number of a curated card, or the Scryfall Oracle ID of any card.'


class CardNumberFilter(ModelMultipleChoiceFilter):
    '''A parameter naming cards by their number, which is the id the API publishes them under.

    Only a curated card can be named: the number is the only id the API gives a card, and a card
    without one takes part in nothing a filter here asks about. The parameter can be repeated, and
    `distinct` is set for the same reason the generated filter this replaces set both: the relation
    reached through a card is a many to many one, so a row would come back once per join that matched.

    The card the number resolved to is what gets compared, rather than the number itself, so that each
    relation is matched on the column it actually stores: the join behind the features of a card holds
    the number, while the join behind the templates a card matches holds the primary key, since a
    template can stand for a card no editor has curated.'''

    def __init__(self, **kwargs):
        kwargs.setdefault('queryset', Card.objects.filter(number__isnull=False))
        kwargs.setdefault('to_field_name', 'number')
        kwargs.setdefault('distinct', True)
        super().__init__(**kwargs)

    def get_filter_predicate(self, v):
        return {self.field_name: v}


class CardReferenceField(ModelMultipleChoiceField):
    '''A field taking cards named by number or by Scryfall Oracle ID, and by nothing else.

    A relation holding cards nobody has curated cannot be asked about by number alone, since those
    cards have none, and the primary key is not published: the oracle id is the other half.'''

    def _check_values(self, value):
        given = [force_str(item).strip() for item in value]
        numbers = set[int]()
        oracle_ids = set[UUID]()
        for reference in given:
            if reference.isdigit():
                numbers.add(int(reference))
                continue
            try:
                oracle_ids.add(UUID(reference))
            except ValueError:
                raise DjangoValidationError(
                    f'“{reference}” is neither a card number nor a Scryfall Oracle ID.',
                    code='invalid_choice',
                )
        available: QuerySet[Card] = self.queryset if self.queryset is not None else Card.objects.all()
        cards = available.filter(Q(number__in=numbers) | Q(oracle_id__in=oracle_ids)).order_by()
        known = set[str]()
        for card in cards:
            known.add(str(card.number))
            known.add(str(card.oracle_id))
        for reference in given:
            if reference.lower() not in known:
                raise DjangoValidationError(f'No card is published as “{reference}”.', code='invalid_choice')
        return cards


class CardReferenceFilter(CardNumberFilter):
    '''A parameter naming cards the way the API publishes them, by number or by Scryfall Oracle ID.

    This is the parameter for a relation reaching any card rather than only a curated one, which is
    why it takes the oracle id as well: the number names the cards an editor took in, and every card
    Scryfall knows answers to its oracle id.'''

    field_class = CardReferenceField

    def __init__(self, **kwargs):
        kwargs.setdefault('queryset', Card.objects.all())
        super().__init__(**kwargs)


class AbstractQueryFilter(filters.BaseFilterBackend):
    search_param = 'q'
    template = 'rest_framework/filters/search.html'
    search_title = 'Search'
    search_description = 'A search query.'

    def query_parser(self, queryset: QuerySet, search_terms: str):
        raise NotImplementedError

    def get_search_terms(self, request) -> str:
        '''
        Search terms are set by a ?q=... query parameter,
        and may be whitespace delimited.
        '''
        params = request.query_params.get(self.search_param, '')
        params = params.replace('\x00', '')  # remove null characters
        return params

    def filter_queryset(self, request, queryset, view):
        search_terms = self.get_search_terms(request)
        try:
            queryset = self.query_parser(queryset, search_terms)
        except DjangoValidationError as e:
            raise ValidationError(detail={self.search_param: e.messages}) from e
        return queryset

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


class SpellbookQueryExplanationFilter(AbstractQueryFilter):
    '''
    A filter backend for the search query of a view that explains it instead of filtering with it,
    leaving the queryset untouched.
    '''
    search_description = 'A search query to explain in plain English.'

    def query_parser(self, queryset, search_terms):
        return queryset


class AutocompleteQueryFilter(AbstractQueryFilter):
    fields: list[str] = []

    def query_parser(self, queryset, search_terms):
        if search_terms == '?':
            return queryset.order_by('?')
        if not search_terms or not self.fields:
            return queryset
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


class AbstractBooleanFilter(filters.BaseFilterBackend):
    '''
    A filter backend for a boolean query parameter that the view reads on its own,
    leaving the queryset untouched.
    '''
    query_param = 'enabled'
    template = 'spellbook/filters/boolean.html'
    title = 'Enabled'
    description = 'A boolean flag.'
    enabled_label = 'Enabled'
    disabled_label = 'Disabled'

    def get_current_value(self, request: Request) -> str | None:
        return request.query_params.get(self.query_param)

    def is_enabled(self, request: Request) -> bool:
        return (self.get_current_value(request) or '').lower() == 'true'

    def filter_queryset(self, request, queryset, view):
        return queryset

    def to_html(self, request, queryset, view):
        context = {
            'request': request,
            'title': force_str(self.title),
            'current': self.get_current_value(request),
            'param': self.query_param,
            'options': [
                ('true', force_str(self.enabled_label)),
                ('false', force_str(self.disabled_label)),
            ]
        }
        template = loader.get_template(self.template)
        return template.render(context)

    def get_schema_operation_parameters(self, view):
        return [
            {
                'name': self.query_param,
                'required': False,
                'in': 'query',
                'description': force_str(self.description),
                'schema': {
                    'type': 'boolean',
                },
            },
        ]


class OrderingFilterWithNullsLast(filters.OrderingFilter):
    def filter_queryset(self, request, queryset: QuerySet, view):
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            ordering_with_nulls: list = []
            for field in ordering:
                if isinstance(field, str):
                    field_name = field.lstrip('-')
                    if field_name == '?':
                        ordering_with_nulls.append('?')
                        continue
                    nulls_last: bool | None = True
                    try:
                        if not queryset.model._meta.get_field(field_name).null:
                            nulls_last = None
                    except FieldDoesNotExist:
                        pass
                    expression = F(field_name)
                    if field.startswith('-'):
                        ordering_with_nulls.append(expression.desc(nulls_last=nulls_last))
                    else:
                        ordering_with_nulls.append(expression.asc(nulls_last=nulls_last))
                else:
                    ordering_with_nulls.append(field)
            return queryset.order_by(*ordering_with_nulls)
        return queryset
