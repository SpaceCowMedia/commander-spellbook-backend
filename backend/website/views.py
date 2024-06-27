from urllib.parse import urlparse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.request import Request
from .models import WebsiteProperty
from .serializers import WebsitePropertySerializer
from .services.moxfield import moxfield, MOXFIELD_HOSTNAME
from .services.archidekt import archidekt, ARCHIDEKT_HOSTNAME


class WebsitePropertyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WebsiteProperty.objects.all()
    serializer_class = WebsitePropertySerializer


SUPPORTED_DECKBUILDING_WEBSITES = {
    MOXFIELD_HOSTNAME: moxfield,
    ARCHIDEKT_HOSTNAME: archidekt,
}


@api_view(['GET'])
@permission_classes([AllowAny])
def card_list_from_url(request: Request) -> Response:
    url = request.query_params.get('url', '')
    try:
        URLValidator()(url)
    except ValidationError:
        return Response({'error': 'Invalid URL'}, status=400)
    parsed_url = urlparse(url)
    hostname = (parsed_url.hostname or '').lower().removeprefix('www.')
    if hostname not in SUPPORTED_DECKBUILDING_WEBSITES:
        return Response({'error': 'Unsupported website'}, status=400)
    deck = SUPPORTED_DECKBUILDING_WEBSITES[hostname](url)
    if deck is None:
        return Response({'error': 'Invalid URL'}, status=400)
    return Response(deck.__dict__)
