from rest_framework import viewsets
from spellbook.models import Variant, PreSerializedSerializer
from .filters import SpellbookQueryFilter, OrderingFilterWithNullsLast


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.serialized_objects.filter(status__in=Variant.public_statuses())
    filter_backends = [SpellbookQueryFilter, OrderingFilterWithNullsLast]
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
