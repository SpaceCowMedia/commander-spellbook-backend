from math import ceil
from collections.abc import Callable
from django.db.models import QuerySet, Count, F, Sum, Window
from django.db.models.functions import FirstValue
from django.http import HttpRequest
from django.template import loader
from rest_framework import viewsets, serializers, filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters.filters import CharFilter
from drf_spectacular.utils import extend_schema, inline_serializer
from spellbook.models import Combo, Variant, PreSerializedSerializer
from spellbook.models.utils import has_random_in_order_by, remove_duplicates_in_order_by, remove_random_from_order_by
from spellbook.models.variant import DEFAULT_VIEW_ORDERING
from spellbook.serializers import VariantSerializer
from .filters import SpellbookQueryFilter, OrderingFilterWithNullsLast


class VariantGroupedByComboFilter(filters.BaseFilterBackend):
    '''Keeps, of the variants each combo generated, the first one in the ordering.

    Ranking every variant to find those firsts costs a sort of them all, which the page size cannot
    cut short. It does not take every variant to rank one, though: the ranking ends with the primary
    key, making it a total order, so which variant of a combo comes first among the highest ranked
    variants is which one comes first overall. Windowing that many of them therefore names the same
    firsts the whole table would, once the window is wide enough to reach the combos the page shows.
    How wide that is can only be estimated, so a window that comes up short of combos gives way to
    one over every variant: an estimate too small costs a second query, never rows.
    '''
    query_param = 'group_by_combo'
    template = 'spellbook/filters/group_by_combo.html'

    def get_current_value(self, request: HttpRequest) -> str | None:
        return request.query_params.get(self.query_param)  # type: ignore

    def filter_queryset(self, request: HttpRequest, queryset: QuerySet[Variant], view: 'VariantViewSet'):
        group_by_params = self.get_current_value(request)
        if group_by_params in ('true', 'True', '1', ''):
            return self.grouped_queryset(queryset, view, self.window_size_for(request, view))
        return queryset

    def window_size_for(self, request: HttpRequest, view: 'VariantViewSet') -> int | None:
        '''How many variants the window has to reach to hold the combos the page shows: one page of
        them, each taking as many variants as a combo has on average. Both aggregates read the one
        indexed column, which keeps the estimate an index only scan. None windows every variant, which
        is what a page reaching every combo takes anyway, and what a count query takes, having to
        reach every combo to count them.'''
        paginator = view.paginator
        if paginator is None or paginator.get_count_query(request):
            return None
        limit = paginator.get_limit(request)
        if limit is None:
            return None
        needed = paginator.get_offset(request) + limit
        combos = Combo.objects.aggregate(count=Count('variant_count'), variants=Sum('variant_count'))
        if not combos['variants'] or needed >= combos['count']:
            return None
        return ceil(needed * combos['variants'] / combos['count'])

    def grouped_queryset(self, queryset: QuerySet[Variant], view: 'VariantViewSet', window_size: int | None) -> QuerySet[Variant]:
        order_by = list(queryset.query.order_by)
        ranking = list(remove_duplicates_in_order_by(remove_random_from_order_by(order_by + list(DEFAULT_VIEW_ORDERING))))  # type: ignore[arg-type]
        if has_random_in_order_by(order_by):  # type: ignore[arg-type]
            window_size = None
        else:
            order_by = ranking
        source = queryset if window_size is None else Variant.objects.filter(pk__in=queryset.order_by(*ranking).values('pk')[:window_size])
        first_variant_of_each_combo = source.alias(
            top_variant=Window(
                expression=FirstValue('pk'),
                partition_by=F('variantofcombo__combo_id'),
                order_by=ranking,
            )
        ).filter(
            pk=F('top_variant'),
        )
        view.widen_combo_window = None if window_size is None else lambda: self.grouped_queryset(queryset, view, None)
        return view.queryset.filter(pk__in=first_variant_of_each_combo).order_by(*order_by)

    def get_schema_operation_parameters(self, view):
        return [
            {
                'name': self.query_param,
                'required': False,
                'in': 'query',
                'description': 'Group variants by combo',
                'schema': {
                    'type': 'boolean',
                },
            },
        ]

    def to_html(self, request, queryset, view):
        context = {
            'request': request,
            'current': self.get_current_value(request),
            'param': self.query_param,
            'options': [
                ('true', 'Group by combo'),
                ('false', 'Do not group by combo'),
            ]
        }
        template = loader.get_template(self.template)
        return template.render(context)


class EditorOrOnlyPublicVariantsFilters(filters.BaseFilterBackend):
    def filter_queryset(self, request: HttpRequest, queryset: QuerySet[Variant], view):
        if hasattr(request, 'user') and request.user.is_authenticated:
            user = request.user
            if user.has_perm('spellbook.change_variant'):  # type: ignore
                return queryset.filter(status__in=Variant.public_statuses() + Variant.preview_statuses())
        return queryset.filter(status__in=Variant.public_statuses())


class VariantFilterSet(FilterSet):
    variant = CharFilter(field_name='of__variants', label='Filters for variants of the same combos that generated the given variant id.', distinct=True)


@extend_schema(responses={
    200: VariantSerializer,
    400: inline_serializer('VariantsQueryValidationError', {
        'q': serializers.ListSerializer(child=serializers.CharField(), required=False),
    })
})
class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.serialized_objects
    widen_combo_window: 'Callable[[], QuerySet[Variant] | None] | None' = None
    filter_backends = [
        EditorOrOnlyPublicVariantsFilters,
        SpellbookQueryFilter,
        OrderingFilterWithNullsLast,
        DjangoFilterBackend,
        VariantGroupedByComboFilter,
    ]
    serializer_class = PreSerializedSerializer
    filterset_class = VariantFilterSet
    ordering = DEFAULT_VIEW_ORDERING
    ordering_fields = [
        'popularity',
        *Variant.prices_fields(),
        'identity_count',
        'result_count',
        'card_count',
        'variant_count',
        'created',
        'updated',
        '?'
    ]

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        if page is not None and self.widen_combo_window is not None and len(page) < self.paginator.limit:
            widened = self.widen_combo_window()
            if widened is not None:
                page = super().paginate_queryset(widened)
        return page
