import re
from urllib.parse import urlparse
from .json_api import get
from common.abstractions import Deck, CardInDeck
from django.conf import settings


MOXFIELD_HOSTNAME = 'moxfield.com'

PATH_REGEX = re.compile(r'^/decks/(?P<id>[\w-]+)')


def moxfield(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    id_match = PATH_REGEX.match(parsed_url.path)
    if id_match is None:
        return None
    id = id_match.group('id')
    api_url = moxfield_id_to_api(id)
    result = get(api_url, settings.MOXFIELD_USER_AGENT)
    if result is None:
        return None
    try:
        main = [
            CardInDeck(card=card, quantity=int(item['quantity']))
            for card, item in result['mainboard'].items()
        ]
        commanders = [
            CardInDeck(card=card, quantity=int(item['quantity']))
            for card, item in result['commanders'].items()
        ]
        return Deck(main=main, commanders=commanders)
    except (KeyError, ValueError, AttributeError):
        return None


def moxfield_id_to_api(id: str) -> str:
    return f'https://api.{MOXFIELD_HOSTNAME}/v2/decks/all/{id}'
