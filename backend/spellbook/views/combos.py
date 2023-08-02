from rest_framework import viewsets
from spellbook.models import Combo
from spellbook.serializers import ComboDetailSerializer
from django_filters.rest_framework import DjangoFilterBackend


class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Combo.objects.exclude(kind=Combo.Kind.DRAFT).prefetch_related(
        'cardincombo_set__card',
        'templateincombo_set__template',
        'cardincombo_set',
        'templateincombo_set',
        'produces',
        'needs')
    serializer_class = ComboDetailSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['kind', 'needs__id']
