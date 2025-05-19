from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import VariantUpdateSuggestion
from spellbook.serializers import VariantUpdateSuggestionSerializer


class IsNewAndOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Assumes the model instance has an `owner` attribute.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.status == VariantUpdateSuggestion.Status.NEW and obj.suggested_by == request.user


class VariantUpdateSuggestionViewSet(viewsets.ModelViewSet):
    queryset = VariantUpdateSuggestionSerializer.prefetch_related(VariantUpdateSuggestion.objects)
    serializer_class = VariantUpdateSuggestionSerializer
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly, IsNewAndOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['suggested_by']
