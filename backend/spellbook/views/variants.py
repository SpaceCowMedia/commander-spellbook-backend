from rest_framework import viewsets
from rest_framework.filters import OrderingFilter
from spellbook.models import Variant
from spellbook.serializers import VariantSerializer
from .query_filters import SpellbookQueryFilter


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.public_statuses()))
    filter_backends = [SpellbookQueryFilter, OrderingFilter]
    serializer_class = VariantSerializer
    ordering_fields = ['identity_count', 'results_count', 'cards_count', 'created', 'updated', '?']
