from rest_framework import viewsets
from spellbook.models import Feature
from spellbook.serializers import FeatureSerializer


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer
