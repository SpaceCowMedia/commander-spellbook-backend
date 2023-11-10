from rest_framework import viewsets
from spellbook.models import Variant
from spellbook.serializers import VariantSerializer
from .query_filters import SpellbookQueryFilter


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = VariantSerializer.prefetch_related(Variant.objects.filter(status__in=Variant.public_statuses()))
    filter_backends = [SpellbookQueryFilter]
    serializer_class = VariantSerializer
