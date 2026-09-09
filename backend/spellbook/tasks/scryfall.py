from collections import defaultdict
from dataclasses import dataclass
import json
import gzip
import uuid
import datetime
from decimal import Decimal
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from django.utils import timezone
from spellbook.models import Card, merge_color_identities, simplify_card_name, simplify_card_name_with_spaces, strip_accents, LayoutRotation
from constants import USER_AGENT


HEADERS = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}


def standardize_name(name: str) -> str:
    return name.lower().strip(' \t\n\r')


@dataclass(frozen=True)
class Scryfall:
    cards: dict[str, dict]
    tags: list[dict]
    taggings: dict[str, frozenset[str]]
    tutor: frozenset[str]
    mass_land_denial: frozenset[str]
    extra_turn: frozenset[str]


def bulk_data(collection: str):
    '''The lines of one Scryfall bulk collection, as the objects they encode.'''
    request = Request(f'https://api.scryfall.com/bulk-data/{collection}?format=json', headers=HEADERS)
    with urlopen(request) as response:
        download = json.loads(response.read().decode())['jsonl_download_uri']
    with urlopen(Request(download, headers=HEADERS)) as response:
        for line in gzip.decompress(response.read()).decode().splitlines():
            yield json.loads(line)


def expand_taggings(tags: list[dict]) -> dict[str, frozenset[str]]:
    '''For each tag, every oracle card carrying it or carrying any tag below it.

    Scryfall rolls a tag up over its descendants, and a tag can have no card of its own: the whole
    membership of removal comes from the twenty five tags underneath it. Resolving that here, once per
    sync, leaves a search for a tag a single lookup.'''
    by_id = {tag['id']: tag for tag in tags}
    ancestors: dict[str, frozenset[str]] = {}

    def ancestors_of(tag_id: str, walked: frozenset[str] = frozenset()) -> frozenset[str]:
        if tag_id in ancestors:
            return ancestors[tag_id]
        if tag_id in walked or tag_id not in by_id:
            return frozenset()
        found = set[str]()
        for parent_id in by_id[tag_id].get('parent_ids', ()):
            if parent_id in by_id:
                found.add(parent_id)
                found |= ancestors_of(parent_id, walked | {tag_id})
        if not walked:
            ancestors[tag_id] = frozenset(found)
        return frozenset(found)

    result = defaultdict[str, set[str]](set)
    for tag in tags:
        tagged = {tagging['oracle_id'] for tagging in tag['taggings']}
        if not tagged:
            continue
        result[tag['id']] |= tagged
        for ancestor_id in ancestors_of(tag['id']):
            result[ancestor_id] |= tagged
    return {tag_id: frozenset(oracle_ids) for tag_id, oracle_ids in result.items()}


def scryfall(bulk_collection: str | None = None) -> Scryfall:
    if bulk_collection is None:
        bulk_collection = 'oracle-cards'
    if bulk_collection not in {'oracle-cards', 'default-cards'}:
        raise ValueError('Invalid bulk collection type')
    # Scryfall card database fetching
    req = Request(
        f'https://api.scryfall.com/bulk-data/{bulk_collection}?format=json',
        headers=HEADERS,
    )
    card_db = dict[str, dict]()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        req = Request(
            data['jsonl_download_uri'],
            headers=HEADERS,
        )
        with urlopen(req) as response:
            for card_raw in gzip.decompress(response.read()).decode().splitlines():
                card = json.loads(card_raw)
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
                        if other_reprint is None or released_at < other_reprint['released_at'] and len(card_and_faces) == 1:
                            card_db[name] = card

    # EDHREC card database fetching
    req = Request(
        'https://json.edhrec.com/static/prices',
        headers=HEADERS,
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
    # Oracle tags, which the bracket attributes below and the template queries are both read out of
    tags = list(bulk_data('oracle_tags'))
    taggings = expand_taggings(tags)
    tagged = {tag['slug']: taggings.get(tag['id'], frozenset()) for tag in tags}
    for tag in tags:
        for alias in tag['aliases']:
            tagged.setdefault(alias, taggings.get(tag['id'], frozenset()))
    # Bracket-related attributes, out of the tags rather than out of a search Scryfall runs for us
    cheap = {card['oracle_id'] for card in card_db.values() if 'oracle_id' in card and int(card['cmc']) <= 3}
    tutor = (tagged.get('tutor', frozenset()) - tagged.get('tutor-land', frozenset()) - tagged.get('tutor-seek', frozenset())) & cheap
    mass_land_denial = tagged.get('mass-land-denial', frozenset())
    extra_turn = tagged.get('extra-turn', frozenset())
    # Other missing data
    req = Request(
        'https://raw.githubusercontent.com/chevEldrid/pdh-json-updater/master/pauper_commander.json',
        headers=HEADERS,
    )
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        for card in data:
            name = card['name']
            paupercommander_legality = 'legal' if card['legality'] == 'Legal' else 'not_legal'
            paupercommander_commander_legality = 'legal' if card['isPauperCommander'] else 'not_legal'
            card_and_faces = [name]
            if ' // ' in name:
                card_and_faces += name.split(' // ')
            for face in card_and_faces:
                name = standardize_name(face)
                if name in card_db:
                    card_db[name]['legalities']['paupercommander'] = paupercommander_legality
                    card_db[name]['legalities']['paupercommander_c'] = paupercommander_commander_legality
        for card in card_db.values():
            if 'paupercommander_c' not in card['legalities']:
                card['legalities']['paupercommander_c'] = 'not_legal'
    return Scryfall(
        cards={name: obj for name, obj in card_db.items() if 'oracle_id' in obj},
        tags=tags,
        taggings=taggings,
        tutor=tutor,
        mass_land_denial=mass_land_denial,
        extra_turn=extra_turn,
    )


def fuzzy_restore_card(scryfall: dict, name: str):
    if name in scryfall:
        return
    req = Request(
        'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': name}),
        headers=HEADERS,
    )
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        actual_name = standardize_name(data['name'])
        if actual_name in scryfall:
            scryfall[name] = scryfall[actual_name]
            return
        else:
            raise Exception(f'Card {name} not found in scryfall dataset, even after fuzzy search')


def unreleased(card_in_db: dict) -> bool:
    return datetime.datetime.strptime(card_in_db['released_at'], '%Y-%m-%d').date() > timezone.now().date()


def never_legal(card_in_db: dict) -> bool:
    '''Whether the card is printed to be playable nowhere, the way an acorn stamped or a silver bordered
    one is, and the way a plane or an emblem is not a deck card to begin with.

    A format that bans or restricts a card still counts it as one of its own, so only the cards no format
    says anything about are caught. An unreleased card is not one of them: every format calls it not legal
    until its set is out, so what it was printed to be is read off its stamp and its border instead.'''
    if any(legality != 'not_legal' for legality in card_in_db['legalities'].values()):
        return False
    return not unreleased(card_in_db) or card_in_db['border_color'] == 'silver' or card_in_db.get('security_stamp') == 'acorn'


def face_field(card_in_db: dict, key: str) -> str:
    '''The characteristic as the card prints it, read off the front face when the card as a whole has none,
    the way a double faced card carries its cost and its power.'''
    value = card_in_db.get(key)
    if value is None:
        faces = card_in_db.get('card_faces', [])
        value = faces[0].get(key) if faces else None
    return value or ''


def apply_scryfall_fields(card: Card, card_in_db: dict, scryfall: Scryfall):
    '''Writes onto the card every field the bulk object decides, leaving its name and number alone.'''
    oracle_id = card_in_db['oracle_id']
    card.identity = merge_color_identities(card_in_db['color_identity'])
    card.color = merge_color_identities(card_in_db['colors'] if 'colors' in card_in_db else card_in_db['card_faces'][0]['colors'])
    card.spoiler = not card_in_db['reprint'] and unreleased(card_in_db)
    card.type_line = card_in_db['type_line']
    card.faces = len(card_in_db['card_faces']) if len(card_in_db.get('card_faces', [])) > 1 else 1
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
    card.legal_pauper_commander = card_legalities['paupercommander_c'] == 'legal' or card.legal_pauper_commander_main
    card.legal_oathbreaker = card_legalities['oathbreaker'] == 'legal'
    card.legal_predh = card_legalities['predh'] == 'legal'
    card.legal_standard_brawl = card_legalities['standardbrawl'] == 'legal'
    card.legal_brawl = card_legalities['brawl'] == 'legal'
    card.legal_competitive_brawl = card_legalities['competitivebrawl'] == 'legal'
    card.legal_alchemy = card_legalities['alchemy'] == 'legal'
    card.legal_vintage = card_legalities['vintage'] in ('legal', 'restricted')
    card.legal_legacy = card_legalities['legacy'] == 'legal'
    card.legal_premodern = card_legalities['premodern'] == 'legal'
    card.legal_modern = card_legalities['modern'] == 'legal'
    card.legal_pioneer = card_legalities['pioneer'] == 'legal'
    card.legal_standard = card_legalities['standard'] == 'legal'
    card.legal_pauper = card_legalities['pauper'] == 'legal'
    # Adjust legalities for spoiled cards
    if card.spoiler:
        future_paper = 'paper' in card_in_db['games']
        future_arena = 'arena' in card_in_db['games']
        future_standard = card_legalities['future'] == 'legal' and future_paper
        future_alchemy = card_legalities['future'] == 'legal' and future_arena
        future_vintage = card_in_db['border_color'] != 'silver' and card_in_db.get('security_stamp', None) != 'acorn' and future_paper
        future_pauper = future_vintage and card_in_db['rarity'] == 'common'
        future_pauper_commander = future_vintage and (
            card_in_db['rarity'] == 'common' or card_in_db['rarity'] == 'uncommon' and (
                'Legendary' in card_in_db['type_line'] or 'can be your commander' in card.oracle_text
            )
        )
        if future_vintage:
            card.legal_commander = card_legalities['commander'] != 'banned'
            card.legal_vintage = card_legalities['vintage'] != 'banned'
            card.legal_legacy = card_legalities['legacy'] != 'banned'
            card.legal_oathbreaker = card_legalities['oathbreaker'] != 'banned'
        if future_pauper_commander:
            card.legal_pauper_commander = card_legalities['paupercommander_c'] != 'banned'
        if future_pauper:
            card.legal_pauper = card_legalities['pauper'] != 'banned'
            card.legal_pauper_commander_main = card_legalities['paupercommander'] != 'banned'
        if future_standard:
            card.legal_standard = card_legalities['standard'] != 'banned'
            card.legal_pioneer = card_legalities['pioneer'] != 'banned'
            card.legal_modern = card_legalities['modern'] != 'banned'
        if future_alchemy:
            card.legal_alchemy = card_legalities['alchemy'] != 'banned'
        if future_standard or future_alchemy:
            card.legal_brawl = card_legalities['brawl'] != 'banned'
            card.legal_standard_brawl = card_legalities['standard_brawl'] != 'banned'
            card.legal_competitive_brawl = card_legalities['competitive_brawl'] != 'banned'
    if 'prices' in card_in_db:
        card_prices = card_in_db['prices']
        p = card_prices['tcgplayer']['price'] if card_prices['tcgplayer'] is not None and card_prices['tcgplayer'].get('price') else 0.0
        card.price_tcgplayer = round(Decimal.from_float(p), 2)
        p = card_prices['cardkingdom']['price'] if card_prices['cardkingdom'] is not None and card_prices['cardkingdom'].get('price') else 0.0
        card.price_cardkingdom = round(Decimal.from_float(p), 2)
        p = card_prices['cardmarket']['price'] if card_prices['cardmarket'] is not None and card_prices['cardmarket'].get('price') else 0.0
        card.price_cardmarket = round(Decimal.from_float(p), 2)
    card.latest_printing_set = card_in_db['set'].lower()
    card.reprinted = card_in_db['reprint']
    if card_in_db['image_status'] != 'missing':
        single_face = bool(card_in_db.get('image_uris')) or 'card_faces' not in card_in_db
        front_images: dict[str, str] = card_in_db.get('image_uris', {}) if single_face else card_in_db['card_faces'][0].get('image_uris', {})
        back_images: dict[str, str] = {} if single_face else card_in_db['card_faces'][1].get('image_uris', {})
        card.image_uri_front_png = front_images.get('png', None)
        card.image_uri_front_large = front_images.get('large', None)
        card.image_uri_front_normal = front_images.get('normal', None)
        card.image_uri_front_small = front_images.get('small', None)
        card.image_uri_front_art_crop = front_images.get('art_crop', None)
        card.image_uri_back_png = back_images.get('png', None)
        card.image_uri_back_large = back_images.get('large', None)
        card.image_uri_back_normal = back_images.get('normal', None)
        card.image_uri_back_small = back_images.get('small', None)
        card.image_uri_back_art_crop = back_images.get('art_crop', None)
    else:
        card.image_uri_front_png = None
        card.image_uri_front_large = None
        card.image_uri_front_normal = None
        card.image_uri_front_small = None
        card.image_uri_front_art_crop = None
        card.image_uri_back_png = None
        card.image_uri_back_large = None
        card.image_uri_back_normal = None
        card.image_uri_back_small = None
        card.image_uri_back_art_crop = None
    match card_in_db['layout']:
        case 'split':
            card.layout_rotation_front = LayoutRotation.COUNTERCLOCKWISE if 'Aftermath' in card_in_db['keywords'] else LayoutRotation.CLOCKWISE
        case 'flip':
            card.layout_rotation_front = LayoutRotation.FLIP
        case _ if card_in_db['type_line'].split(' ', 1)[0] == 'Battle':
            card.layout_rotation_front = LayoutRotation.CLOCKWISE
    card.mana_cost = face_field(card_in_db, 'mana_cost')
    card.power = face_field(card_in_db, 'power')
    card.toughness = face_field(card_in_db, 'toughness')
    card.loyalty = face_field(card_in_db, 'loyalty')
    card.layout = card_in_db['layout']
    produced = set(card_in_db.get('produced_mana') or [])
    for face in card_in_db.get('card_faces', []):
        produced.update(face.get('produced_mana') or [])
    card.produced_mana = sorted(produced)


def scryfall_fields_of(card: Card) -> tuple:
    return tuple(getattr(card, field) for field in Card.scryfall_fields() + Card.playable_fields())


def name_keys(name: str) -> tuple[str, str, str, str]:
    '''The four names a card is unique by, so that a collision is caught before the database rejects it.

    Each one is a column of its own, so they are compared one to one: the same string under two
    different keys is two different cards, not a clash.'''
    unaccented = strip_accents(name)
    return name, unaccented, simplify_card_name(unaccented), simplify_card_name_with_spaces(unaccented)


def update_cards(cards: list[Card], scryfall: Scryfall, log=lambda t: print(t), log_warning=lambda t: print(t), log_error=lambda t: print(t), progress=lambda fraction: None) -> tuple[list[Card], list[Card], list[Card]]:
    '''The cards whose fields the bulk data changes, the oracle cards the database does not hold yet, and
    the ones it should never have taken in.

    The second list is what grows the table to the whole oracle universe: those cards get no number,
    so nothing can reference them until an editor curates one, and a card no format was ever meant to
    allow is not among them. The third is that same growth undone, for the cards an earlier run added
    before they were ruled out. Only what an editor curated is safe from it, and keeps being updated
    like any other card.'''
    oracle_db = {card_object['oracle_id']: card_object for card_object in scryfall.cards.values()}
    existing_names = {card.name: card for card in cards}
    existing_oracle_ids = {card.oracle_id: card for card in cards if card.oracle_id is not None}
    cards_to_save: list[Card] = []
    cards_to_delete: list[Card] = []
    card_count = len(cards)
    for i, card in enumerate(cards):
        progress(i / card_count / 2)
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
            if card.number is None and never_legal(card_in_db):
                cards_to_delete.append(card)
                continue
            card_name = card_in_db['name']
            if card.name != card_name:
                if card_name in existing_names:
                    log_error(f'Card {card.name} would have a the same name as another card with oracle id {existing_names[card_name].oracle_id}, skipping name update')
                else:
                    card.name = card_in_db['name']
                    updated = True
            fields_before = scryfall_fields_of(card)
            apply_scryfall_fields(card, card_in_db, scryfall)
            if fields_before != scryfall_fields_of(card):
                updated = True
        else:
            log_warning(f'Card {card.name} with oracle id {oracle_id} not found in scryfall dataset. Oracle id has been removed.')
            card.oracle_id = None
            updated = True
        if updated:
            cards_to_save.append(card)
    known_oracle_ids = {str(card.oracle_id) for card in cards if card.oracle_id is not None}
    taken_names = [set(keys) for keys in zip(*(name_keys(card.name) for card in cards))]
    cards_to_create: list[Card] = []
    missing = [oracle_id for oracle_id in oracle_db if oracle_id not in known_oracle_ids]
    missing_count = len(missing) or 1
    for i, oracle_id in enumerate(missing):
        progress(0.5 + i / missing_count / 2)
        card_in_db = oracle_db[oracle_id]
        if never_legal(card_in_db):
            continue
        keys = name_keys(card_in_db['name'])
        if any(key in taken for key, taken in zip(keys, taken_names)):
            log_warning(f'Oracle card {card_in_db["name"]} is named as a card already in the database, and is not being added')
            continue
        for key, taken in zip(keys, taken_names):
            taken.add(key)
        card = Card(oracle_id=uuid.UUID(hex=oracle_id), name=card_in_db['name'])
        apply_scryfall_fields(card, card_in_db, scryfall)
        cards_to_create.append(card)
    return cards_to_save, cards_to_create, cards_to_delete
