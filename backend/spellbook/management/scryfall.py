import json
import uuid
import datetime
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from django.utils import timezone
from spellbook.models import Card, merge_identities


def standardize_name(name: str) -> str:
    return name.lower().strip(' \t\n\r')


def scryfall():
    # Scryfall card database fetching
    req = Request(
        'https://api.scryfall.com/bulk-data/oracle-cards?format=json'
    )
    card_db = dict[str, dict]()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        req = Request(
            data['download_uri'],
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'}
        )
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            for card in data:
                name = standardize_name(card['name'])
                if name not in card_db \
                    and (any(card['legalities'][format] != 'not_legal' for format in ['commander', 'vintage', 'oathbreaker', 'brawl', 'predh']) or any(game in card['games'] for game in ['paper', 'arena', 'mtgo'])) \
                        and card['layout'] not in {'art_series', 'vanguard', 'scheme', 'token'}:
                    card_db[name] = card
                    if 'card_faces' in card and len(card['card_faces']) > 1:
                        for face in card['card_faces']:
                            card_db[standardize_name(face['name'])] = card

    # EDHREC card database fetching
    req = Request(
        'https://json.edhrec.com/static/prices'
    )
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        # Avoid conflicts with scryfall data
        for card in card_db.values():
            card.pop('prices', None)
        for name, prices in data.items():
            name = standardize_name(name)
            if name in card_db:
                card_db[name]['prices'] = prices
    return {name: obj for name, obj in card_db.items() if 'oracle_id' in obj}


def fuzzy_restore_card(scryfall: dict, name: str):
    if name in scryfall:
        return
    req = Request(
        'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': name}))
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        actual_name = standardize_name(data['name'])
        if actual_name in scryfall:
            scryfall[name] = scryfall[actual_name]
            return
        else:
            raise Exception(f'Card {name} not found in scryfall dataset, even after fuzzy search')


def update_cards(cards: list[Card], scryfall: dict[str, dict], log=lambda t: print(t), log_warning=lambda t: print(t), log_error=lambda t: print(t)):
    oracle_db = {card_object['oracle_id']: card_object for card_object in scryfall.values()}
    existing_names = {card.name: card for card in cards}
    existing_oracle_ids = {card.oracle_id: card for card in cards if card.oracle_id is not None}
    cards_to_save: list[Card] = []
    for card in cards:
        updated = False
        if card.oracle_id is None:
            log(f'Card {card.name} lacks an oracle_id: attempting to find it by name...')
            card_name = standardize_name(card.name)
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

            def card_fields(card: Card) -> tuple:
                return tuple(getattr(card, field) for field in Card.scryfall_fields() + Card.playable_fields())
            fields_before = card_fields(card)
            card_identity = merge_identities(card_in_db['color_identity'])
            card.identity = card_identity
            card_spoiler = card_in_db['legalities']['commander'] != 'legal' \
                and not card_in_db['reprint'] \
                and datetime.datetime.strptime(card_in_db['released_at'], '%Y-%m-%d').date() > timezone.now().date()
            card.type_line = card_in_db['type_line']
            if 'card_faces' in card_in_db:
                card.oracle_text = '\n\n'.join(face['oracle_text'] for face in card_in_db['card_faces'])
            else:
                card.oracle_text = card_in_db['oracle_text']
            card.keywords = card_in_db['keywords']
            card.mana_value = int(card_in_db['cmc'])
            card.reserved = card_in_db['reserved']
            card.spoiler = card_spoiler
            card_legalities = card_in_db['legalities']
            card.legal_commander = card_legalities['commander'] == 'legal'
            card.legal_pauper_commander_main = card_legalities['paupercommander'] == 'legal'
            card.legal_pauper_commander = card_legalities['paupercommander'] in ('legal', 'restricted')
            card.legal_oathbreaker = card_legalities['oathbreaker'] == 'legal'
            card.legal_predh = card_legalities['predh'] == 'legal'
            card.legal_brawl = card_legalities['brawl'] == 'legal'
            card.legal_vintage = card_legalities['vintage'] == 'legal'
            card.legal_legacy = card_legalities['legacy'] == 'legal'
            card.legal_modern = card_legalities['modern'] == 'legal'
            card.legal_pioneer = card_legalities['pioneer'] == 'legal'
            card.legal_standard = card_legalities['standard'] == 'legal'
            card.legal_pauper = card_legalities['pauper'] == 'legal'
            card_prices = card_in_db['prices']
            p = card_prices['tcgplayer']['price'] if card_prices['tcgplayer'] is not None else 0.0
            card.price_tcgplayer = round(Decimal.from_float(p), 2)
            p = card_prices['cardkingdom']['price'] if card_prices['cardkingdom'] is not None else 0.0
            card.price_cardkingdom = round(Decimal.from_float(p), 2)
            p = card_prices['cardmarket']['price'] if card_prices['cardmarket'] is not None else 0.0
            card.price_cardmarket = round(Decimal.from_float(p), 2)
            card.latest_printing_set = card_in_db['set'].lower()
            card.reprinted = card_in_db['reprint']
            fields_after = card_fields(card)
            if fields_before != fields_after:
                updated = True
        else:
            log_warning(f'Card {card.name} with oracle id {oracle_id} not found in scryfall dataset. Oracle id has been removed.')
            card.oracle_id = None
            updated = True
        if updated:
            cards_to_save.append(card)
    return cards_to_save
