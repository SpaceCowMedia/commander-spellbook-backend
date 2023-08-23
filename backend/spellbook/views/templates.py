from rest_framework import viewsets
from spellbook.models import Template
from spellbook.serializers import TemplateSerializer
from .query_filters import NameAndScryfallAutocompleteQueryFilter


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer
    filter_backends = [NameAndScryfallAutocompleteQueryFilter]
