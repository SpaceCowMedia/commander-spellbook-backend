from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Feature
from spellbook.serializers import FeatureSerializer
from .query_filters import NameAndDescriptionAutocompleteQueryFilter


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FeatureSerializer.prefetch_related(Feature.objects)
    serializer_class = FeatureSerializer
    filter_backends = [NameAndDescriptionAutocompleteQueryFilter, DjangoFilterBackend]
    filterset_fields = ['utility']
