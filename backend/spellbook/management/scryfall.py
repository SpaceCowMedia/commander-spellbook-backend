import json
import uuid
import datetime
from urllib.request import Request, urlopen
from django.utils import timezone
from spellbook.models import Card
from spellbook.variants.list_utils import merge_identities


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


def update_cards(cards: list[Card], scryfall: dict[str, object], log=lambda t: print(t), log_warning=lambda t: print(t), log_error=lambda t: print(t)):
    oracle_db = {card_object['oracle_id']: card_object for card_object in scryfall.values()}
    existing_names = {card.name: card for card in cards}
    existing_oracle_ids = {card.oracle_id: card for card in cards if card.oracle_id is not None}
    cards_to_save: list[Card] = []
    for card in cards:
        updated = False
        if card.oracle_id is None:
            log(f'Card {card.name} lacks an oracle_id: attempting to find it by name...')
            card_name = card.name.lower().strip(' \t\n\r')
            if card_name in scryfall:
                card.oracle_id = uuid.UUID(hex=scryfall[card_name]['oracle_id'])
                if card.oracle_id in existing_oracle_ids:
                    log_error(f'Card {card.name} would have the same oracle id as {existing_oracle_ids[card.oracle_id].name}, skipping')
                    continue
                updated = True
                log(f'Card {card.name} found in scryfall dataset, oracle_id set to {card.oracle_id}')
            else:
                log_warning(f'Card {card.name} not found in scryfall dataset, after searching by name')
                continue
        oracle_id = str(card.oracle_id)
        if oracle_id in oracle_db:
            card_in_db = oracle_db[oracle_id]
            card_name = card_in_db['name']
            if card.name != card_name:
                if card_name in existing_names:
                    log_error(f'Card {card.name} would have a the same name as another card with oracle id {existing_names[card_name].oracle_id}, skipping name update')
                else:
                    card.name = card_in_db['name']
                    updated = True
            card_identity = merge_identities(card_in_db['color_identity'])
            if card.identity != card_identity:
                card.identity = card_identity
                updated = True
            card_legal = card_in_db['legalities']['commander'] != 'banned'
            if card.legal != card_legal:
                card.legal = card_legal
                updated = True
            card_spoiler = card_in_db['legalities']['commander'] != 'legal' \
                and not card_in_db['reprint'] \
                and datetime.datetime.strptime(card_in_db['released_at'], '%Y-%m-%d').date() > timezone.now().date()
            if card.spoiler != card_spoiler:
                card.spoiler = card_spoiler
                updated = True
        else:
            log_warning(f'Card {card.name} with oracle id {oracle_id} not found in scryfall dataset. Oracle id has been removed.')
            card.oracle_id = None
            updated = True
        if updated:
            cards_to_save.append(card)
    return cards_to_save
