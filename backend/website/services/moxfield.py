import re
from urllib.parse import urlparse
from .json_api import get
from common.abstractions import Deck


MOXFIELD_HOSTNAME = 'moxfield.com'

PATH_REGEX = re.compile(r'^/decks/(?P<id>[\w-]+)')


def moxfield(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    id_match = PATH_REGEX.match(parsed_url.path)
    if id_match is None:
        return None
    id = id_match.group('id')
    api_url = moxfield_id_to_api(id)
    result = get(api_url)
    if result is None:
        return None
    try:
        main = [card for card in result['mainboard']]
        commanders = [card for card in result['commanders']]
        return Deck(main=main, commanders=commanders)
    except KeyError:
        return None


def moxfield_id_to_api(id: str) -> str:
    return f'https://api.{MOXFIELD_HOSTNAME}/v2/decks/all/{id}'
