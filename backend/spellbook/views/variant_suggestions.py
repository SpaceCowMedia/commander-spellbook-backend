from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import VariantSuggestion
from spellbook.serializers import VariantSuggestionSerializer


class IsNewAndOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.status == VariantSuggestion.Status.NEW and obj.suggested_by == request.user


class VariantSuggestionViewSet(viewsets.ModelViewSet):
    queryset = VariantSuggestionSerializer.prefetch_related(VariantSuggestion.objects)
    serializer_class = VariantSuggestionSerializer
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly, IsNewAndOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['suggested_by']
