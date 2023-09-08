from rest_framework.viewsets import ModelViewSet
from rest_framework import permissions
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


class VariantSuggestionViewSet(ModelViewSet):
    queryset = VariantSuggestionSerializer.prefetch_related(VariantSuggestion.objects)
    serializer_class = VariantSuggestionSerializer
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly, IsNewAndOwnerOrReadOnly]
