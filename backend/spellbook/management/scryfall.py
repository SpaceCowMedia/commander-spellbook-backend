from dataclasses import dataclass
import json
import uuid
import datetime
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.parse import quote_plus, urlencode
from django.utils import timezone
from spellbook.models import Card, merge_identities


def standardize_name(name: str) -> str:
    return name.lower().strip(' \t\n\r')


@dataclass(frozen=True)
class Scryfall:
    cards: dict[str, dict]
    tutor: frozenset[str]
    mass_land_denial: frozenset[str]
    extra_turn: frozenset[str]


def scryfall(bulk_collection: str | None = None) -> Scryfall:
    if bulk_collection is None:
        bulk_collection = 'oracle-cards'
    if bulk_collection not in {'oracle-cards', 'default-cards'}:
        raise ValueError('Invalid bulk collection type')
    # Scryfall card database fetching
    req = Request(
        f'https://api.scryfall.com/bulk-data/{bulk_collection}?format=json'
    )
    card_db = dict[str, dict]()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        req = Request(
            data['download_uri'],  # type: ignore
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0'}
        )
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            for card in data:
                if (any(game in card['games'] for game in ['paper', 'arena', 'mtgo']) or not card['games']) and card['layout'] not in {'art_series', 'vanguard', 'scheme', 'token'}:
                    card_and_faces = [card]
                    faces = card.get('card_faces', [])
                    if len(faces) > 1:
                        card_and_faces += faces
                    released_at = card['released_at']
                    for face in card_and_faces:
                        # Fix for double faced cards
                        face['released_at'] = released_at
                        name = standardize_name(face['name'])
                        other_reprint = card_db.get(name, None)
                        if other_reprint is None or released_at < other_reprint['released_at']:
                            card_db[name] = card

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
    tutor = get_tagged_cards_from_scryfall('function:tutor -function:tutor-land -function:tutor-seek mv<=3')
    mass_land_denial = get_tagged_cards_from_scryfall('function:sweeper-land-destroy')
    extra_turn = get_tagged_cards_from_scryfall('function:extra-turn')
    return Scryfall(
        cards={name: obj for name, obj in card_db.items() if 'oracle_id' in obj},
        tutor=tutor,
        mass_land_denial=mass_land_denial,
        extra_turn=extra_turn,
    )


def get_tagged_cards_from_scryfall(q: str) -> frozenset[str]:
    req = Request(f'https://api.scryfall.com/cards/search?format=json&q={quote_plus(q)}')
    has_next = True
    result = set[str]()
    max_pages = 10
    while has_next and max_pages > 0:
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            has_next = data['has_more']
            if has_next:
                req = Request(data['next_page'])
            for card in data['data']:
                card_and_faces = [card]
                faces = card.get('card_faces', [])
                if len(faces) > 1:
                    card_and_faces += faces
                for face in card_and_faces:
                    if 'oracle_id' in face:
                        result.add(face['oracle_id'])
        max_pages -= 1
    return frozenset(result)


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


def update_cards(cards: list[Card], scryfall: Scryfall, counts: dict[int, int], log=lambda t: print(t), log_warning=lambda t: print(t), log_error=lambda t: print(t)):
    oracle_db = {card_object['oracle_id']: card_object for card_object in scryfall.cards.values()}
    existing_names = {card.name: card for card in cards}
    existing_oracle_ids = {card.oracle_id: card for card in cards if card.oracle_id is not None}
    cards_to_save: list[Card] = []
    for card in cards:
        updated = False
        if card.oracle_id is None:
            log(f'Card {card.name} lacks an oracle_id: attempting to find it by name...')
            card_name = standardize_name(card.name)
            if card_name in scryfall.cards:
                card.oracle_id = uuid.UUID(hex=scryfall.cards[card_name]['oracle_id'])
                if card.oracle_id in existing_oracle_ids:
                    log_error(f'Card {card.name} would have the same oracle id as {existing_oracle_ids[card.oracle_id].name}, skipping')  # type: ignore
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
            card.spoiler = not card_in_db['reprint'] \
                and datetime.datetime.strptime(card_in_db['released_at'], '%Y-%m-%d').date() > timezone.now().date()
            card.type_line = card_in_db['type_line']
            if 'card_faces' in card_in_db:
                card.oracle_text = '\n\n'.join(face['oracle_text'] for face in card_in_db['card_faces'])
            else:
                card.oracle_text = card_in_db['oracle_text']
            card.keywords = card_in_db['keywords']
            card.mana_value = int(card_in_db['cmc'])
            card.reserved = card_in_db['reserved']
            card.tutor = oracle_id in scryfall.tutor
            card.mass_land_denial = oracle_id in scryfall.mass_land_denial
            card.extra_turn = oracle_id in scryfall.extra_turn
            card.game_changer = card_in_db['game_changer']
            card_legalities = card_in_db['legalities']
            card.legal_commander = card_legalities['commander'] == 'legal'
            card.legal_pauper_commander_main = card_legalities['paupercommander'] == 'legal'
            card.legal_pauper_commander = card_legalities['paupercommander'] in ('legal', 'restricted')
            card.legal_oathbreaker = card_legalities['oathbreaker'] == 'legal'
            card.legal_predh = card_legalities['predh'] == 'legal'
            card.legal_brawl = card_legalities['brawl'] == 'legal'
            card.legal_vintage = card_legalities['vintage'] in ('legal', 'restricted')
            card.legal_legacy = card_legalities['legacy'] == 'legal'
            card.legal_premodern = card_legalities['premodern'] == 'legal'
            card.legal_modern = card_legalities['modern'] == 'legal'
            card.legal_pioneer = card_legalities['pioneer'] == 'legal'
            card.legal_standard = card_legalities['standard'] == 'legal'
            card.legal_pauper = card_legalities['pauper'] == 'legal'
            # Adjust legalities for spoiled cards
            if card.spoiler:
                future_standard = card_legalities['future'] == 'legal'
                future_commander = card_in_db['border_color'] != 'silver' and card_in_db.get('security_stamp', None) != 'acorn'
                future_pauper = future_commander and card_in_db['rarity'] == 'common'
                future_pauper_commander = future_commander and (
                    card_in_db['rarity'] == 'common' or card_in_db['rarity'] == 'uncommon' and (
                        'Legendary' in card_in_db['type_line'] or 'can be your commander' in card.oracle_text
                    )
                )
                if future_commander:
                    card.legal_commander = True
                    card.legal_vintage = True
                    card.legal_legacy = True
                    card.legal_oathbreaker = True
                if future_pauper_commander:
                    card.legal_pauper_commander = True
                if future_pauper:
                    card.legal_pauper = True
                    card.legal_pauper_commander_main = True
                if future_standard:
                    card.legal_standard = True
                    card.legal_pioneer = True
                    card.legal_modern = True
                    card.legal_brawl = True
            if 'prices' in card_in_db:
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
        variant_count = counts.get(card.id, 0)
        if card.variant_count != variant_count:
            card.variant_count = variant_count
            updated = True
        if updated:
            cards_to_save.append(card)
    return cards_to_save
