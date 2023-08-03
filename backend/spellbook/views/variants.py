from rest_framework import viewsets
from spellbook.models import Variant
from spellbook.serializers import VariantSerializer
from .query_filters import SpellbookQueryFilter


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.objects.filter(status__in=(Variant.Status.OK, Variant.Status.EXAMPLE)).prefetch_related(
        'cardinvariant_set__card',
        'templateinvariant_set__template',
        'cardinvariant_set',
        'templateinvariant_set',
        'produces',
        'of',
        'includes')
    filter_backends = [SpellbookQueryFilter]
    serializer_class = VariantSerializer
