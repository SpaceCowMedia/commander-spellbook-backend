from rest_framework import viewsets
from spellbook.models import Combo
from spellbook.serializers import ComboDetailSerializer
from django_filters.rest_framework import DjangoFilterBackend


class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ComboDetailSerializer.prefetch_related(Combo.objects.exclude(kind=Combo.Kind.DRAFT))
    serializer_class = ComboDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kind', 'needs__id']
