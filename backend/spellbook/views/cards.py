from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Card
from spellbook.serializers import CardDetailSerializer
from .filters import NameAutocompleteQueryFilter, OrderingFilterWithNullsLast


class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CardDetailSerializer.prefetch_related(Card.objects)
    serializer_class = CardDetailSerializer
    ordering_fields = ['variant_count', 'name']
    filter_backends = [DjangoFilterBackend, NameAutocompleteQueryFilter, OrderingFilterWithNullsLast]
    filterset_fields = ['replaces']
