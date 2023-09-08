from rest_framework import viewsets
from spellbook.models import Card
from spellbook.serializers import CardDetailSerializer
from .query_filters import NameAutocompleteQueryFilter


class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CardDetailSerializer.prefetch_related(Card.objects)
    serializer_class = CardDetailSerializer
    filter_backends = [NameAutocompleteQueryFilter]
