from rest_framework import viewsets
from spellbook.models import Combo
from spellbook.serializers import ComboDetailSerializer


class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Combo.objects.prefetch_related(
        'cardincombo_set__card',
        'templateincombo_set__template',
        'cardincombo_set',
        'templateincombo_set',
        'produces',
        'needs')
    serializer_class = ComboDetailSerializer
