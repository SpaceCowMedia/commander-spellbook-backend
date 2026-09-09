from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from spellbook.models import Template
from spellbook.serializers import TemplateSerializer
from .filters import CardNumberFilter, NameAndScryfallAutocompleteQueryFilter


class TemplateFilterSet(FilterSet):
    matches = CardNumberFilter(field_name='matches', label='Filters for the templates standing for the cards with the given numbers.')


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TemplateSerializer.prefetch_related(Template.objects.all())
    serializer_class = TemplateSerializer
    filter_backends = [DjangoFilterBackend, NameAndScryfallAutocompleteQueryFilter]
    filterset_class = TemplateFilterSet
