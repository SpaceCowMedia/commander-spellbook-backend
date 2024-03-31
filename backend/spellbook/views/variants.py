from rest_framework import viewsets
from spellbook.models import Variant, PreSerializedSerializer
from .filters import SpellbookQueryFilter, OrderingFilterWithNullsLast


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.serialized_objects
    filter_backends = [SpellbookQueryFilter, OrderingFilterWithNullsLast]
    serializer_class = PreSerializedSerializer
    ordering_fields = [
        'popularity',
        *Variant.prices_fields(),
        'identity_count',
        'results_count',
        'cards_count',
        'mana_value_needed',
        'created',
        'updated',
        '?'
    ]

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(self, 'request') and hasattr(self.request, 'user') and self.request.user.is_authenticated:
            user = self.request.user
            if user.has_perm('spellbook.change_variant'):  # type: ignore
                return queryset.filter(status__in=Variant.public_statuses() + Variant.preview_statuses())
        return queryset.filter(status__in=Variant.public_statuses())
