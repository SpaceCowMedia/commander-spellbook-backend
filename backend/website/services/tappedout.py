import re
from urllib.parse import urlparse
from .csv_api import get
from common.abstractions import Deck


TAPPEDOUT_HOSTNAME = 'tappedout.net'

PATH_REGEX = re.compile(r'^/mtg-decks/(?P<id>[\w-]+)')


def tappedout(url: str) -> Deck | None:
    parsed_url = urlparse(url)
    id_match = PATH_REGEX.match(parsed_url.path)
    if id_match is None:
        return None
    id = id_match.group('id')
    api_url = tappedout_id_to_api(id)
    result = get(api_url)
    if result is None:
        return None
    try:
        main = []
        commanders = []
        for row in result:
            if row['Board'] == 'main':
                name = row['Name']
                if 'Commander' in row and row['Commander'] == 'True':
                    commanders.append(name)
                else:
                    main.append(name)
        return Deck(main=main, commanders=commanders)
    except KeyError:
        return None


def tappedout_id_to_api(id: str) -> str:
    return f'https://{TAPPEDOUT_HOSTNAME}/mtg-decks/{id}/?fmt=csv'
