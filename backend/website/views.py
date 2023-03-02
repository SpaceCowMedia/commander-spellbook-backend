from rest_framework import viewsets
from .models import WebsiteProperty
from .serializers import WebsitePropertySerializer


class WebsitePropertyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WebsiteProperty.objects.all()
    serializer_class = WebsitePropertySerializer
