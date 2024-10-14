from django.db.models import QuerySet, F, Window
from django.db.models.functions import Rank
from django.http import HttpRequest
from django.template import loader
from rest_framework import viewsets, serializers, filters
from drf_spectacular.utils import extend_schema, inline_serializer
from spellbook.models import Variant, PreSerializedSerializer
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
        top_variants_for_each_combo = queryset.annotate(
            rank=Window(
                expression=Rank(),
                partition_by=F('variantofcombo__combo_id'),
                order_by=queryset.query.order_by,
            )
        ).filter(rank=1).values('id').distinct()
        return queryset.filter(id__in=top_variants_for_each_combo)

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


@extend_schema(responses={
    200: VariantSerializer,
    400: inline_serializer('VariantsQueryValidationError', {
        'q': serializers.ListSerializer(child=serializers.CharField(), required=False),
    })
})
class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.serialized_objects
    filter_backends = [SpellbookQueryFilter, OrderingFilterWithNullsLast, VariantGroupedByComboFilter]
    serializer_class = PreSerializedSerializer
    ordering_fields = [
        'popularity',
        *Variant.prices_fields(),
        'identity_count',
        'result_count',
        'card_count',
        'mana_value_needed',
        'description_line_count',
        'other_prerequisites_line_count',
        'created',
        'updated',
        '?'
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self, 'request') and hasattr(self.request, 'user') and self.request.user.is_authenticated:
            user = self.request.user
            if user.has_perm('spellbook.change_variant'):
                return queryset.filter(status__in=Variant.public_statuses() + Variant.preview_statuses())
        return queryset.filter(status__in=Variant.public_statuses())
