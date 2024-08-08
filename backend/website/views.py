from urllib.parse import urlparse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.exceptions import APIException
from drf_spectacular.utils import extend_schema, OpenApiParameter
from common.serializers import DeckSerializer
from .models import WebsiteProperty
from .serializers import WebsitePropertySerializer
from .services.moxfield import moxfield, MOXFIELD_HOSTNAME
from .services.archidekt import archidekt, ARCHIDEKT_HOSTNAME
from .services.deckstats import deckstats, DECKSTATS_HOSTNAME
from .services.tappedout import tappedout, TAPPEDOUT_HOSTNAME


class WebsitePropertyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WebsiteProperty.objects.all()
    serializer_class = WebsitePropertySerializer


SUPPORTED_DECKBUILDING_WEBSITES = {
    MOXFIELD_HOSTNAME: moxfield,
    ARCHIDEKT_HOSTNAME: archidekt,
    DECKSTATS_HOSTNAME: deckstats,
    TAPPEDOUT_HOSTNAME: tappedout,
}


class InvalidUrl(APIException):
    status_code = 400
    default_detail = 'Invalid URL'
    default_code = 'invalid_url'


class UnsupportedWebsite(APIException):
    status_code = 400
    default_detail = 'Unsupported website'
    default_code = 'unsupported_website'


@extend_schema(
    parameters=[OpenApiParameter(name='url', type=str)],
    responses=DeckSerializer,
)
@api_view(['GET'])
@permission_classes([AllowAny])
def card_list_from_url(request: Request) -> Response:
    url = request.query_params.get('url', '')
    try:
        URLValidator()(url)
    except ValidationError:
        raise InvalidUrl()
    parsed_url = urlparse(url)
    hostname = (parsed_url.hostname or '').lower().removeprefix('www.')
    if hostname not in SUPPORTED_DECKBUILDING_WEBSITES:
        raise UnsupportedWebsite()
    deck = SUPPORTED_DECKBUILDING_WEBSITES[hostname](url)
    if deck is None:
        raise UnsupportedWebsite()
    return Response(DeckSerializer(deck).data)
