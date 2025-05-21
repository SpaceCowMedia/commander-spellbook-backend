from rest_framework.request import Request
from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Suggestion
from spellbook.views.validation import ValidationMixin


class IsNewAndOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request: Request, view, obj: Suggestion):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.status == Suggestion.Status.NEW and obj.suggested_by == request.user


class SuggestionViewSet(ValidationMixin, viewsets.ModelViewSet):
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly, IsNewAndOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['suggested_by']
