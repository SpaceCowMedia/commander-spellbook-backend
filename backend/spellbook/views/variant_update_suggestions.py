from spellbook.models import VariantUpdateSuggestion
from spellbook.serializers import VariantUpdateSuggestionSerializer
from .suggestions import SuggestionViewSet


class VariantUpdateSuggestionViewSet(SuggestionViewSet):
    queryset = VariantUpdateSuggestionSerializer.prefetch_related(VariantUpdateSuggestion.objects)
    serializer_class = VariantUpdateSuggestionSerializer
