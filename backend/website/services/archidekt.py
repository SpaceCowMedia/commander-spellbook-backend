import re
from urllib.parse import urlparse
from .json_api import get
from common.abstractions import Deck, CardInDeck

ARCHIDEKT_HOSTNAME = 'archidekt.com'

PATH_REGEX = re.compile(r'^/decks/(?P<id>\d+)')


def archidekt(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    id_match = PATH_REGEX.match(parsed_url.path)
    if id_match is None:
        return None
    id = id_match.group('id')
    api_url = archidekt_id_to_api(id)
    result = get(api_url)
    if result is None:
        return None
    try:
        cards_with_quantity_and_categories: dict[str, tuple[int, set[str]]] = {
            card['card']['oracleCard']['name']: (card['quantity'] or 1, {c.lower() for c in card['categories'] or []})
            for card in result['cards']
        }
        main = [
            CardInDeck(card=card, quantity=quantity)
            for card, (quantity, categories) in cards_with_quantity_and_categories.items()
            if 'commander' not in categories and 'sideboard' not in categories and 'maybeboard' not in categories and 'considering' not in categories
        ]
        commanders = [
            CardInDeck(card=card, quantity=quantity)
            for card, (quantity, categories) in cards_with_quantity_and_categories.items()
            if 'commander' in categories
        ]
        return Deck(main=main, commanders=commanders)
    except KeyError:
        return None


def archidekt_id_to_api(id: str) -> str:
    return f'https://{ARCHIDEKT_HOSTNAME}/api/decks/{id}/'
