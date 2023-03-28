import json
import gzip
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dataclasses import dataclass
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from spellbook.variants.variants_generator import id_from_cards_and_templates_ids, generate_variants
from spellbook.models import Feature, Card, Job, Combo, CardInCombo, Variant, IngredientInCombination
from spellbook.models.validators import MANA_SYMBOL
from ..scryfall import scryfall, update_cards


@dataclass(frozen=True)
class ImportedVariantBulkSaveItem:
    combo: Combo
    uses: list[CardInCombo]
    produces: list[Feature]


def find_combos() -> list[tuple[str, frozenset[str], frozenset[str], str, str, str]]:
    """Fetches the combos from the google sheet.
    Result format: id, cards, produced, prerequisite, description, mana"""
    combosdb = dict[frozenset[str], frozenset[str]]()
    combosdata = dict[frozenset[str], tuple[str, str]]()
    combos_reverse_id = dict[frozenset[str], str]()
    # Commander Spellbook database fetching
    req = Request(
        'https://sheets.googleapis.com/v4/spreadsheets/1KqyDRZRCgy8YgMFnY0tHSw_3jC99Z0zFvJrPbfm66vA/values:batchGet?ranges=combos!A2:Q&key=AIzaSyBD_rcme5Ff37Evxa4eW5BFQZkmTbgpHew')
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        for row in data['valueRanges'][0]['values']:
            cards = frozenset(map(lambda name: name.lower().strip(' \t\n\r'), filter(
                lambda name: name is not None and len(name) > 0, row[1:11]))) - set([''])
            if len(cards) <= 1:
                continue
            combos_reverse_id[cards] = row[0]
            pros = [token.replace('.', '') for token in row[14].lower().strip(' \t\n\r').split('. ')]
            combosdb[cards] = frozenset(pros)
            combosdata[cards] = (row[12], row[13])
    result = []
    for card_set in combosdb:
        features = frozenset(combosdb[card_set])
        prerequisites = combosdata[card_set][0]
        mana_match = re.match(r'^(.*?)\s*((?:\{' + MANA_SYMBOL + r'\})+) available[^\w].*$', prerequisites, re.IGNORECASE)
        mana = ''
        if mana_match:
            prerequisites = mana_match.group(1)
            mana = mana_match.group(2).upper()
        positions_dict = {}
        new_prerequisites = prerequisites
        def sorted_prereq_search_terms(prereq: str, card_set: set[str]):
            pre_lower = prereq.lower()
            terms = card_set | {'all permanents', 'all other permanents', 'all other cards', 'all cards'}
            return sorted((c for c in terms if c.lower() in pre_lower), key=lambda x: pre_lower.index(x.lower()))
        for c in sorted_prereq_search_terms(prerequisites, card_set):
            positions = re.findall(c + r' ([^,\.]+)(.?)', prerequisites, re.IGNORECASE)
            for position in positions:
                p_list = list[IngredientInCombination.ZoneLocation]()
                if re.search(r'(?:[^\w]|^)hand(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.HAND)
                if re.search(r'(?:[^\w]|^)battlefield(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.BATTLEFIELD)
                if re.search(r'(?:[^\w]|^)command zone(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.COMMAND_ZONE)
                if re.search(r'(?:[^\w]|^)graveyard(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.GRAVEYARD)
                if re.search(r'(?:[^\w]|^)exiled?(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.EXILE)
                if re.search(r'(?:[^\w]|^)library(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list.append(IngredientInCombination.ZoneLocation.LIBRARY)
                if re.search(r'(?:[^\w]|^)any(?:[^\w]|$)', position[0], re.IGNORECASE) \
                    or re.search(r'(?:[^\w]|^)or(?:[^\w]|$)', position[0], re.IGNORECASE):
                    p_list = [IngredientInCombination.ZoneLocation.ANY]
                if len(p_list) == 1:
                    if c in positions_dict:
                        raise Exception(f'Found duplicate positioning for {c} in {prerequisites}')
                    positions_dict[c] = p_list[0]
                    if position[1] == '.' and positions_dict[c] != IngredientInCombination.ZoneLocation.ANY:
                        new_prerequisites = re.subn(c + r' ([^,\.]+)\.', '', new_prerequisites, 1, re.IGNORECASE)[0].strip()
                elif len(p_list) > 1:
                    raise Exception(f'Found {len(p_list)} positions for {c} in {prerequisites}')
        description = combosdata[card_set][1]
        result.append((combos_reverse_id[card_set], card_set, features, prerequisites, description, mana))
    return result


class Command(BaseCommand):
    help = 'Tries to import combos from the google sheet'

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        job.message += message + '\n'
        job.save(update_fields=['message'])

    def update_and_load_cards(self, job, x) -> dict[str, Card]:
        self.log_job(job, 'Fetching combos...done')
        self.log_job(job, 'Fetching scryfall dataset...')
        scryfall_db = scryfall()
        self.log_job(job, 'Fetching scryfall dataset...done')
        cards_from_combos: set[str] = {c.lower() for t in x for c in t[1]}
        self.log_job(job, f'Found {len(cards_from_combos)} cards, updating cards in database...')
        spellbook_cards = list(Card.objects.all())
        oracle_cards_in_database = {str(c.oracle_id): c for c in spellbook_cards}
        name_cards_in_database = {c.name: c for c in spellbook_cards}
        combo_card_name_to_card = dict[str, Card]()
        for i, card in enumerate(cards_from_combos):
            self.stdout.write(f'{i+1}/{len(cards_from_combos)} {card}')
            if card in scryfall_db:
                data = scryfall_db[card]
            else:
                self.log_job(job, f'Card {card} not found in Scryfall JSON, fetching...')
                scryreq = Request(
                    'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': card}))
                with urlopen(scryreq) as response:
                    data = json.loads(response.read().decode())
                    scryfall_db[card] = data
                self.log_job(job, f'Card {card} fetched')
            save_card = False
            if data['oracle_id'] in oracle_cards_in_database:
                c = oracle_cards_in_database[data['oracle_id']]
            elif data['name'] in name_cards_in_database:
                c = name_cards_in_database[data['name']]
                c.oracle_id = data['oracle_id']
                save_card = True
            else:
                c = Card.objects.create(name=data['name'], oracle_id=data['oracle_id'])
                oracle_cards_in_database[str(c.oracle_id)] = c
                name_cards_in_database[c.name] = c
                save_card = True
            updated_cards = update_cards(
                [c],
                scryfall_db,
                lambda x: self.log_job(job, x),
                lambda x: self.log_job(job, x, self.style.WARNING),
                lambda x: self.log_job(job, x, self.style.ERROR),
            )
            if len(updated_cards) > 0:
                c = updated_cards[0]
                save_card = True
            if save_card:
                self.stdout.write(f'Updating card {c.name}...')
                c.save()
                oracle_cards_in_database[str(c.oracle_id)] = c
                name_cards_in_database[c.name] = c
                self.stdout.write(f'Updating card {c.name}...done')
            combo_card_name_to_card[card] = c
        self.log_job(job, 'Done fetching cards')
        return combo_card_name_to_card

    def handle(self, *args, **options):
        job = Job.start('import_combos')
        if job is None:
            self.stdout.write(self.style.ERROR('Job already running'))
            return
        job.save()
        try:
            self.log_job(job, 'Fetching combos...')
            x = find_combos()
            self.log_job(job, 'Found {} combos'.format(len(x)))
            combo_card_name_to_card = self.update_and_load_cards(job, x)
            self.log_job(job, 'Importing combos...')
            with transaction.atomic(durable=True):
                bulk_combo_dict = dict[str, ImportedVariantBulkSaveItem]()
                existing_unique_ids = {id_from_cards_and_templates_ids([c.id for c in combo.uses.all()], []) for combo in Combo.objects.prefetch_related('uses')}
                existing_feature_names = {f.name: f for f in Feature.objects.all()}
                variant_id_map = dict[int, str]()
                next_id = (Combo.objects.aggregate(Max('id'))['id__max'] or 0) + 1
                for i, (old_id, _cards, produced, prerequisite, description, mana_needed) in enumerate(x):
                    self.stdout.write(f'{i+1}/{len(x)}\n' if (i + 1) % 100 == 0 else '.', ending='')
                    cards_from_combo = [combo_card_name_to_card[card] for card in _cards]
                    id = id_from_cards_and_templates_ids([c.id for c in cards_from_combo], [])
                    old_id = int(old_id)
                    variant_id_map[old_id] = id
                    if id in existing_unique_ids:
                        self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in variants')
                        continue
                    if id in bulk_combo_dict:
                        self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in imported variants')
                        continue
                    combo = Combo(
                        id=next_id,
                        other_prerequisites=prerequisite,
                        description=description,
                        generator=True,
                        mana_needed=mana_needed,
                    )
                    next_id += 1
                    produces_dict = {}
                    for name in (p.strip().title() for p in produced):
                        if name in produces_dict:
                            continue
                        if name in existing_feature_names:
                            produces_dict[name] = existing_feature_names[name]
                        else:
                            feature = Feature(name=name)
                            feature.save()
                            produces_dict[name] = feature
                            existing_feature_names[name] = feature
                    produces = list(produces_dict.values())
                    used_cards = list({c: CardInCombo(card=c, combo=combo, order=i) for i, c in enumerate(cards_from_combo)}.values())
                    bulk_item = ImportedVariantBulkSaveItem(
                        combo=combo,
                        uses=used_cards,
                        produces=produces,
                    )
                    bulk_combo_dict[id] = bulk_item
                self.log_job(job, 'Saving combos...')
                Combo.objects.bulk_create(b.combo for b in bulk_combo_dict.values())
                CardInCombo.objects.bulk_create(b for item in bulk_combo_dict.values() for b in item.uses)
                ProducesTable = Combo.produces.through
                ProducesTable.objects.bulk_create(ProducesTable(combo=item.combo, feature=f) for item in bulk_combo_dict.values() for f in item.produces)
                self.log_job(job, 'Saving combos...done')
            self.log_job(job, 'Saving variant id map...')
            variant_id_map_file: Path = settings.STATIC_BULK_FOLDER / 'variant_id_map.json'
            output = variant_id_map_file.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                json.dump(variant_id_map, f)
                json.dump(variant_id_map, fz)
            self.log_job(job, 'Saving variant id map...done')
            self.log_job(job, 'Generating variants...')
            added, restored, deleted = generate_variants(job)
            self.log_job(job, f'Generating variants...done. Added {added} variants, restored {restored} variants, deleted {deleted} variants.')
            Variant.objects.filter(id__in=bulk_combo_dict.keys()).update(status=Variant.Status.OK)
            self.log_job(job, f'Successfully imported {len(bulk_combo_dict)}/{len(x)} combos. The rest was already present.', self.style.SUCCESS)
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.save()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = f'Failed to import combos: {e}'
            job.save()
            print(e)
            raise e
