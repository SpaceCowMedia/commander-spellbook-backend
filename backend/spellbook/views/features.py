from rest_framework import viewsets
from spellbook.models import Feature
from spellbook.serializers import FeatureSerializer
from .query_filters import NameAndDescriptionAutocompleteQueryFilter


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeatureSerializer.prefetch_related(Feature.objects.filter(utility=False))
    serializer_class = FeatureSerializer
    filter_backends = [NameAndDescriptionAutocompleteQueryFilter]
