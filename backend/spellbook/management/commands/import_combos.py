import json
import gzip
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from spellbook.variants.variants_generator import id_from_cards_and_templates_ids, VariantBulkSaveItem, perform_bulk_saves, restore_variant, RestoreData
from spellbook.variants.list_utils import merge_identities
from spellbook.models import Feature, Card, Job, Variant, CardInVariant
from ..scryfall import scryfall, update_cards


def find_combos() -> list[tuple[str, frozenset[str], frozenset[str], str, str]]:
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
    for c in combosdb:
        features = frozenset(combosdb[c])
        result.append((combos_reverse_id[c], c, features, combosdata[c][0], combosdata[c][1]))
    return result


class Command(BaseCommand):
    help = 'Tries to import combos from the google sheet'

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        job.message += message + '\n'
        job.save()

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
                save_card = True
            if save_card:
                updated_cards = update_cards(
                    [c],
                    scryfall_db,
                    lambda x: self.log_job(job, x),
                    lambda x: self.log_job(job, x, self.style.WARNING),
                    lambda x: self.log_job(job, x, self.style.ERROR),
                )
                if len(updated_cards) > 0:
                    self.log_job(job, f'Updating card {c.name}...')
                    c = updated_cards[0]
                    c.save()
                    self.log_job(job, f'Updating card {c.name}...done')
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
            bulk_variant_dict = dict[str, VariantBulkSaveItem]()
            variant_id_map = dict[int, str]()
            spellbook_features = {f.name: f for f in Feature.objects.all()}
            existing_unique_ids = {v.id for v in Variant.objects.all()}
            data = RestoreData()
            for i, (old_id, _cards, produced, prerequisite, description) in enumerate(x):
                self.stdout.write(f'{i+1}/{len(x)}\n' if (i + 1) % 100 == 0 else '.', ending='')
                cards_from_combo = [combo_card_name_to_card[card] for card in _cards]
                id = id_from_cards_and_templates_ids([c.id for c in cards_from_combo], [])
                variant_id_map[int(old_id)] = id
                if id in existing_unique_ids:
                    self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in variants')
                    continue
                if id in bulk_variant_dict:
                    self.stdout.write(f'\nSkipping combo [{id}] {cards_from_combo}: already present in imported variants')
                    continue
                combo = Variant(other_prerequisites=prerequisite,
                    description=description,
                    frozen=True,
                    status=Variant.Status.OK,
                    id=id,
                    identity=merge_identities([c.identity for c in cards_from_combo]))
                feature_names = {p.strip().title() for p in produced}
                for feature_name in feature_names:
                    if feature_name not in spellbook_features:
                        f = Feature.objects.create(name=feature_name)
                        f.save()
                        spellbook_features[feature_name] = f
                produces = {spellbook_features[feature_name] for feature_name in feature_names}
                used_cards = [CardInVariant(card=c, variant=combo, order=i) for i, c in enumerate(cards_from_combo)]
                used_cards, _ = restore_variant(
                    combo,
                    included_combos=[],
                    generator_combos=[],
                    used_cards=used_cards,
                    required_templates=[],
                    data=data)
                bulk_item = VariantBulkSaveItem(
                    should_update=True,
                    variant=combo,
                    uses=used_cards,
                    requires=[],
                    of=set(),
                    includes=set(),
                    produces={f.id for f in produces})
                bulk_variant_dict[bulk_item.variant.id] = bulk_item
            self.log_job(job, 'Saving combos...')
            perform_bulk_saves(to_create=list(bulk_variant_dict.values()), to_update=[])
            self.log_job(job, 'Saving combos...done')
            self.log_job(job, 'Saving variant id map...')
            variant_id_map_file: Path = settings.STATIC_BULK_FOLDER / 'variant_id_map.json'
            output = variant_id_map_file.resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('w', encoding='utf8') as f, gzip.open(str(output) + '.gz', mode='wt', encoding='utf8') as fz:
                json.dump(variant_id_map, f)
                json.dump(variant_id_map, fz)
            self.log_job(job, 'Saving variant id map...done')
            self.log_job(job, f'Successfully imported {len(bulk_variant_dict)}/{len(x)} combos. The rest was already present.', self.style.SUCCESS)
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
