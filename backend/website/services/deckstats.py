import re
from urllib.parse import urlparse
from .json_api import get
from common.abstractions import Deck


DECKSTATS_HOSTNAME = 'deckstats.net'

PATH_REGEX = re.compile(r'^/decks/(?P<owner>\d+)/(?P<deck>\d+)')


def deckstats(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    match = PATH_REGEX.match(parsed_url.path)
    if match is None:
        return None
    owner = match.group('owner')
    deck = match.group('deck')
    api_url = deckstats_to_api(owner, deck)
    result = get(api_url)
    if result is None:
        return None
    try:
        main = []
        commanders = []
        for section in result['sections']:
            if section['name'].startswith('Command'):
                for card in section['cards']:
                    if card['valid']:
                        commanders.append(card['name'])
            else:
                for card in section['cards']:
                    if card['valid']:
                        name = card['name']
                        if 'isCommander' in card and card['isCommander']:
                            commanders.append(name)
                        else:
                            main.append(name)
        return Deck(main=main, commanders=commanders)
    except KeyError:
        return None


def deckstats_to_api(owner: str, deck: str) -> str:
    return f'https://{DECKSTATS_HOSTNAME}/api.php?action=get_deck&id_type=saved&owner_id={owner}&id={deck}&response_type=json'
