from django.contrib.auth import get_user_model
from rest_framework import permissions, viewsets, serializers, mixins


class IsSelf(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user and request.user.is_active


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'password', 'email', 'is_staff', 'is_active', 'first_name', 'last_name']
        extra_kwargs = {
            'username': {'read_only': True},
            'password': {'write_only': True},
            'email': {'read_only': True},
            'is_staff': {'read_only': True},
            'is_active': {'read_only': True},
        }


class UserViewSet(
        mixins.RetrieveModelMixin,
        mixins.UpdateModelMixin,
        mixins.DestroyModelMixin,
        mixins.ListModelMixin,
        viewsets.GenericViewSet):
    serializer_class = UserSerializer
    permission_classes = [IsSelf]

    def get_queryset(self):
        return User.objects.filter(id=self.request.user.id)
