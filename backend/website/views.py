from urllib.parse import urlparse
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from rest_framework import viewsets, serializers, parsers
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.exceptions import APIException
from drf_spectacular.utils import extend_schema, OpenApiParameter, inline_serializer
from common.serializers import DeckSerializer
from common.abstractions import Deck
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


class DecklistNotAvailable(APIException):
    status_code = 400
    default_detail = 'Decklist not available'
    default_code = 'decklist_not_available'


class SomethingWentWrong(APIException):
    status_code = 400
    default_detail = 'Something went wrong'
    default_code = 'something_went_wrong'


@extend_schema(
    parameters=[OpenApiParameter(name='url', type=str)],
    responses={
        200: DeckSerializer,
        400: inline_serializer(
            'InvalidUrlResponse',
            fields={
                'detail': serializers.CharField(),
            },
        )
    },
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
    try:
        deck = SUPPORTED_DECKBUILDING_WEBSITES[hostname](url)
        if deck is None:
            raise DecklistNotAvailable()
    except ValidationError as e:
        raise SomethingWentWrong(detail=str(e))
    return Response(DeckSerializer(deck).data)


class PlainTextDeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None) -> str:
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        text = stream.read().decode(encoding)
        return text


@extend_schema(
    request=str,
    responses=DeckSerializer,
)
@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@parser_classes([PlainTextDeckListParser])
def card_list_from_text(request: Request) -> Response:
    data = request.data
    if not data:
        return Response(DeckSerializer(Deck(main=[], commanders=[])).data)
    serializer = DeckSerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return Response(serializer.data)
