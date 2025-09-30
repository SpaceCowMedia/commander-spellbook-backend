from django.db.models import QuerySet, F, Window
from django.db.models.functions import FirstValue
from django.http import HttpRequest
from django.template import loader
from rest_framework import viewsets, serializers, filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from django_filters.filters import CharFilter
from drf_spectacular.utils import extend_schema, inline_serializer
from spellbook.models import Variant, PreSerializedSerializer
from spellbook.models.utils import remove_duplicates_in_order_by
from spellbook.models.variant import DEFAULT_VIEW_ORDERING
from spellbook.serializers import VariantSerializer
from .filters import SpellbookQueryFilter, OrderingFilterWithNullsLast


class VariantGroupedByComboFilter(filters.BaseFilterBackend):
    query_param = 'group_by_combo'
    template = 'spellbook/filters/group_by_combo.html'

    def get_current_value(self, request: HttpRequest) -> str | None:
        return request.query_params.get(self.query_param)  # type: ignore

    def filter_queryset(self, request: HttpRequest, queryset: QuerySet[Variant], view):
        group_by_params = self.get_current_value(request)
        if group_by_params in ('true', 'True', '1', ''):
            return self._filter_queryset(queryset)
        return queryset

    def _filter_queryset(self, queryset: QuerySet[Variant]) -> QuerySet[Variant]:
        order_by = queryset.query.order_by + DEFAULT_VIEW_ORDERING
        order_by = list(remove_duplicates_in_order_by(order_by))
        top_variants_for_each_combo = queryset.alias(
            top_variant=Window(
                expression=FirstValue('pk'),
                partition_by=F('variantofcombo__combo_id'),
                order_by=order_by,
            )
        ).filter(
            pk=F('top_variant'),
        )
        return Variant.serialized_objects.filter(
            pk__in=top_variants_for_each_combo
        ).order_by(
            *queryset.query.order_by
        )

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
