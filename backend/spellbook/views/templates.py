from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Template
from spellbook.serializers import TemplateSerializer
from .filters import NameAndScryfallAutocompleteQueryFilter


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TemplateSerializer.prefetch_related(Template.objects.all())
    serializer_class = TemplateSerializer
    filter_backends = [DjangoFilterBackend, NameAndScryfallAutocompleteQueryFilter]
    filterset_fields = ['replacements']
