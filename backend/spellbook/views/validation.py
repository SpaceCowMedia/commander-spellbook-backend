from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.serializers import BaseSerializer


class ValidationMixin:
    validation_path = 'validate'

    @action(detail=False, methods=['POST'], url_path=validation_path)
    def validate_create(self, request: Request, *args, **kwargs):
        """
        Validate the variant suggestion data.
        """
        serializer = self.get_serializer(data=request.data)  # type: ignore
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)  # type: ignore
        return Response(serializer.data, status=status.HTTP_200_OK, headers=headers)

    @action(detail=True, methods=['PUT', 'PATCH'], url_path=validation_path)
    def validate_update(self, request: Request, pk=None):
        """
        Validate the variant suggestion update data.
        """
        partial = request.method == 'PATCH'
        instance = self.get_object()  # type: ignore
        serializer: BaseSerializer = self.get_serializer(instance, data=request.data, partial=partial)  # type: ignore
        serializer.is_valid(raise_exception=True)
        headers = self.get_success_headers(serializer.data)  # type: ignore
        return Response(serializer.data | serializer.to_representation(serializer.validated_data), status=status.HTTP_200_OK, headers=headers)
