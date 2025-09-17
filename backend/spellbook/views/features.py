from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Feature
from spellbook.serializers import FeatureSerializer
from .filters import NameAndDescriptionAutocompleteQueryFilter


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeatureSerializer.prefetch_related(Feature.objects.exclude(status=Feature.Status.HIDDEN_UTILITY))
    serializer_class = FeatureSerializer
    filter_backends = [DjangoFilterBackend, NameAndDescriptionAutocompleteQueryFilter]
    filterset_fields = ['status']
