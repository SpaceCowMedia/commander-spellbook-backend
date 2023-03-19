import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from spellbook.variants.variants_generator import id_from_cards_and_templates_ids, VariantBulkSaveItem, perform_bulk_saves
from spellbook.variants.list_utils import merge_identities
from spellbook.models import Feature, Card, Job, Variant
from ..scryfall import scryfall


def find_combos():
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

    def handle(self, *args, **options):
        job = Job.start('import_combos')
        if job is None:
            self.stdout.write('Job already running')
            return
        job.save()
        try:
            self.stdout.write('Fetching combos...')
            x = find_combos()
            self.stdout.write('Found {} combos'.format(len(x)))
            self.stdout.write('Fetching scryfall dataset...')
            scryfall_db = scryfall()
            self.stdout.write('Fetching scryfall dataset...done')
            cards = {c.lower() for t in x for c in t[1]}
            cards_db_cache = dict[str, Card]()
            self.stdout.write(f'Found {len(cards)} cards, fetching new ones from Scryfall...')
            for i, card in enumerate(cards):
                self.stdout.write(f'{i+1}/{len(cards)} {card}')
                if card in scryfall_db:
                    data = scryfall_db[card]
                else:
                    self.stdout.write(f'Card {card} not found in Scryfall JSON, fetching...')
                    scryreq = Request(
                        'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': card}))
                    with urlopen(scryreq) as response:
                        data = json.loads(response.read().decode())
                        scryfall_db[card] = data
                c = None
                try:
                    c = Card.objects.get(oracle_id=data['oracle_id'])
                except Card.DoesNotExist:
                    q = Card.objects.filter(name=data['name'])
                    common_kwargs = {
                        'oracle_id': data['oracle_id'],
                        'identity': merge_identities(data['color_identity']),
                        'legal': data['legalities']['commander'] != 'banned'
                    }
                    if q.exists():
                        q.update(**common_kwargs)
                        c = q.first()
                    else:
                        c = Card.objects.create(name=data['name'], **common_kwargs)
                cards_db_cache[str(c.oracle_id)] = c
            self.stdout.write('Done fetching cards')
            self.stdout.write('Importing combos...')
            bulk_variant_dict = dict[str, VariantBulkSaveItem]()
            for i, (id, _cards, produced, prerequisite, description) in enumerate(x):
                self.stdout.write(f'{i+1}/{len(x)}\n' if (i + 1) % 100 == 0 else '.', ending='')
                cards = [cards_db_cache[scryfall_db[card.lower()]['oracle_id']] for card in _cards]
                id = id_from_cards_and_templates_ids([c.id for c in cards], [])
                already_present = Variant.objects.annotate(
                    total_cards=Count('uses'),
                    matching_cards=Count('uses', filter=Q(uses__in=cards)),
                ).filter(
                    total_cards=len(cards),
                    matching_cards=len(cards),
                )
                if already_present.exists():
                    self.stdout.write(f'\nSkipping combo [{id}] {cards}: already present in variants')
                    continue
                if id in bulk_variant_dict:
                    self.stdout.write(f'\nSkipping combo [{id}] {cards}: already present in imported variants')
                    continue
                combo = Variant(other_prerequisites=prerequisite,
                    description=description,
                    frozen=True,
                    status=Variant.Status.OK,
                    id=id,
                    identity=merge_identities([c.identity for c in cards]))
                produces = set()
                for p in produced:
                    try:
                        f = Feature.objects.get(name=p.title())
                    except Feature.DoesNotExist:
                        f = Feature.objects.create(name=p.title())
                    if f not in produces:
                        produces.add(f)
                bulk_item = VariantBulkSaveItem(should_save=True,
                    variant=combo,
                    uses=[c.id for c in cards],
                    requires=[],
                    of=set(),
                    includes=set(),
                    produces={f.id for f in produces})
                bulk_variant_dict[bulk_item.variant.id] = bulk_item
            self.stdout.write('Saving combos...')
            perform_bulk_saves(to_create=list(bulk_variant_dict.values()), to_update=[])
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.message = f'Successfully imported {len(x)} combos'
            job.save()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = f'Failed to import combos: {e}'
            job.save()
            print(e)
            raise e
