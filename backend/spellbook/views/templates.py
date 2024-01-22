from rest_framework import viewsets
from spellbook.models import Template
from spellbook.serializers import TemplateSerializer
from .filters import NameAndScryfallAutocompleteQueryFilter


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TemplateSerializer.prefetch_related(Template.objects)
    serializer_class = TemplateSerializer
    filter_backends = [NameAndScryfallAutocompleteQueryFilter]
