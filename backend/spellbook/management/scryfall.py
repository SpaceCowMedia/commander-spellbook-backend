import json
from urllib.request import Request, urlopen


def scryfall():
    req = Request(
        'https://api.scryfall.com/bulk-data/oracle-cards?format=json'
    )
    # Scryfall card database fetching
    card_db = dict[str, object]()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        req = Request(
            data['download_uri'],
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'}
        )
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            for card in data:
                name = card['name'].lower().strip(' \t\n\r')
                if name not in card_db \
                    and ('paper' in card['games'] or 'mtgo' in card['games']) \
                        and card['layout'] not in {'art_series', 'vanguard', 'scheme'}:
                    card_db[name] = card
                    if 'card_faces' in card and len(card['card_faces']) > 1:
                        for face in card['card_faces']:
                            card_db[face['name'].lower().strip(' \t\n\r')] = card
    return card_db
