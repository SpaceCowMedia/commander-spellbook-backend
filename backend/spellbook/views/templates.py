from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from spellbook.models import Template
from spellbook.serializers import TemplateDetailSerializer
from .filters import CARD_REFERENCE_HELP, CardReferenceFilter, NameAndScryfallAutocompleteQueryFilter, OrderingFilterWithNullsLast


class TemplateFilterSet(FilterSet):
    matches = CardReferenceFilter(field_name='matches', label='Filters for the templates standing for the given cards.')


@extend_schema_view(
    list=extend_schema(parameters=[
        OpenApiParameter(
            name='matches',
            location=OpenApiParameter.QUERY,
            type=str,
            many=True,
            description=f'Filters for the templates standing for the given cards. {CARD_REFERENCE_HELP}',
        ),
    ]),
)
class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TemplateDetailSerializer.prefetch_related(Template.objects.all())
    serializer_class = TemplateDetailSerializer
    ordering_fields = ['variant_count', 'name']
    filter_backends = [DjangoFilterBackend, NameAndScryfallAutocompleteQueryFilter, OrderingFilterWithNullsLast]
    filterset_class = TemplateFilterSet
