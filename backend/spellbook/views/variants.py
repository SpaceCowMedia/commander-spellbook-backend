from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from spellbook.models import Variant, PreSerializedSerializer
from .query_filters import SpellbookQueryFilter


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.serialized_objects.filter(status__in=Variant.public_statuses())
    filter_backends = [SpellbookQueryFilter, OrderingFilter]
    serializer_class = PreSerializedSerializer
    ordering_fields = [
        'popularity',
        *Variant.prices_fields(),
        'identity_count',
        'results_count',
        'cards_count',
        'created',
        'updated',
        '?'
    ]
