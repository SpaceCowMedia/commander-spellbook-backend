from spellbook.models import VariantSuggestion
from spellbook.serializers import VariantSuggestionSerializer
from .suggestions import SuggestionViewSet


class VariantSuggestionViewSet(SuggestionViewSet):
    queryset = VariantSuggestionSerializer.prefetch_related(VariantSuggestion.objects)
    serializer_class = VariantSuggestionSerializer
