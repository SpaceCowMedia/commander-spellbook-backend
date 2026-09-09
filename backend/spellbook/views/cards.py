from uuid import UUID
from rest_framework import viewsets
from rest_framework.generics import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from spellbook.models import Card
from spellbook.serializers import CardDetailSerializer
from .filters import CARD_REFERENCE_HELP, NameAutocompleteQueryFilter, OrderingFilterWithNullsLast


@extend_schema_view(
    retrieve=extend_schema(parameters=[
        OpenApiParameter(
            name='id',
            location=OpenApiParameter.PATH,
            type=str,
            description=CARD_REFERENCE_HELP,
        ),
    ]),
)
class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CardDetailSerializer.prefetch_related(Card.objects.all())
    serializer_class = CardDetailSerializer
    lookup_field = 'number'
    lookup_url_kwarg = 'pk'
    ordering_fields = ['variant_count', 'name']
    filter_backends = [DjangoFilterBackend, NameAutocompleteQueryFilter, OrderingFilterWithNullsLast]
    filterset_fields = ['matched_by']

    def get_object(self):
        value = self.kwargs[self.lookup_url_kwarg]
        try:
            # a card no editor has curated has no number, so its oracle id is the only way to address it
            lookup = {'oracle_id': UUID(value)}
        except ValueError:
            lookup = {self.lookup_field: value}
        card = get_object_or_404(self.filter_queryset(self.get_queryset()), **lookup)
        self.check_object_permissions(self.request, card)
        return card
