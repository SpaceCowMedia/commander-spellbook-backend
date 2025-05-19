from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from spellbook.models import Suggestion


class IsNewAndOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request: Request, view, obj: Suggestion):
        if request.method in permissions.SAFE_METHODS:
            return True

        return obj.status == Suggestion.Status.NEW and obj.suggested_by == request.user


class SuggestionViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.DjangoModelPermissionsOrAnonReadOnly, IsNewAndOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['suggested_by']

    @action(detail=False, methods=['POST'])
    def validate(self, request: Request, *args, **kwargs):
        """
        Validate the variant suggestion data.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)
