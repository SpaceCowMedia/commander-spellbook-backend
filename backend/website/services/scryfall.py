import re
from urllib.parse import urlparse
from .json_api import get
from common.abstractions import Deck, CardInDeck
from django.core.exceptions import ValidationError


SCRYFALL_HOSTNAME = 'scryfall.com'

PATH_REGEX = re.compile(r'^/@(?P<user>[\w-]+)/decks/(?P<id>[\w-]+)')


def scryfall(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    id_match = PATH_REGEX.match(parsed_url.path)
    if id_match is None:
        return None
    id = id_match.group('id')
    api_url = scryfall_id_to_api(id)
    result = get(api_url)
    if result is None:
        return None
    try:
        main = []
        commanders = []
        for key, entries in result['entries'].items():
            if 'commander' in key.lower():
                bucket = commanders
            else:
                bucket = main
            for entry in entries:
                if entry.get('card_digest') is None:
                    continue
                card = entry['card_digest']['name']
                quantity = entry['count']
                bucket.append(CardInDeck(card=card, quantity=int(quantity)))
        return Deck(main=main, commanders=commanders)
    except (KeyError, ValueError, AttributeError):
        raise ValidationError('Invalid decklist')


def scryfall_id_to_api(id: str) -> str:
    return f'https://api.{SCRYFALL_HOSTNAME}/decks/{id}/export/json'
