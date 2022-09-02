from collections import defaultdict
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from django.core.management.base import BaseCommand, CommandError
from spellbook.variants import unique_id_from_cards_ids
from spellbook.models import Feature, Card, Job, Variant
from django.utils import timezone
from django.db.models import Count, Q


def scryfall() -> dict:
    req = Request(
        'https://api.scryfall.com/bulk-data/oracle-cards?format=json'
    )
    # Scryfall card database fetching
    card_db = dict()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        req = Request(
            data['download_uri']
        )
        with urlopen(req) as response:
            data = json.loads(response.read().decode())
            for card in data:
                card_db[card['name'].lower().strip(' \t\n\r')] = card
                if 'card_faces' in card and len(card['card_faces']) > 1:
                    for face in card['card_faces']:
                        card_db[face['name'].lower().strip(' \t\n\r')] = card
    return card_db


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
        job = Job(name='import_combos', expected_termination=timezone.now() + timezone.timedelta(minutes=3))
        job.save()
        try:
            self.stdout.write('Importing combos...')
            x = find_combos()
            self.stdout.write('Found {} combos'.format(len(x)))
            self.stdout.write('Fetching scryfall dataset...')
            scryfall_db = scryfall()
            self.stdout.write('Fetching scryfall dataset...done')
            cards = {c.lower() for t in x for c in t[1]}
            self.stdout.write(f'Found {len(cards)} cards, fetching new ones from Scryfall...')
            for i, card in enumerate(cards):
                self.stdout.write(f'{i+1}/{len(cards)} {card}')
                if card in scryfall_db:
                    data = scryfall_db[card]
                else:
                    scryreq = Request(
                        'https://api.scryfall.com/cards/named?' + urlencode({'fuzzy': card}))
                    with urlopen(scryreq) as response:
                        data = json.loads(response.read().decode())
                        scryfall_db[card] = data
                try:
                    Card.objects.get(oracle_id=data['oracle_id'])
                except Card.DoesNotExist:
                    q = Card.objects.filter(name=data['name'])
                    if q.exists():
                        q.update(oracle_id=data['oracle_id'])
                    else:
                        Card.objects.create(name=data['name'], oracle_id=data['oracle_id'])
            self.stdout.write('Done fetching cards')
            self.stdout.write('Importing combos...')
            for i, (id, _cards, produced, prerequisite, description) in enumerate(x):
                self.stdout.write(f'{i+1}/{len(x)}')
                cards = [Card.objects.get(oracle_id=scryfall_db[card.lower()]['oracle_id']) for card in _cards]
                already_present = Variant.objects.annotate(
                    total_cards=Count('includes'),
                    matching_cards=Count('includes', filter=Q(includes__in=cards)),
                ).filter(
                    total_cards=len(cards),
                    matching_cards=len(cards),
                )
                if already_present.exists():
                    self.stdout.write(f'Skipping combo [{id}] {cards}: already present in variants')
                    continue
                combo = Variant(prerequisites=prerequisite, description=description, frozen=True, unique_id=unique_id_from_cards_ids([c.id for c in cards]))
                combo.save()
                combo.includes.set(cards)
                for p in produced:
                    try:
                        f = Feature.objects.get(name=p.title())
                    except Feature.DoesNotExist:
                        f = Feature.objects.create(name=p.title())
                    if f not in combo.produces.all():
                        combo.produces.add(f)
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.message = f'Successfully imported {len(x)} combos'
            job.save()
        except Exception as e:
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = f'Failed to import combos: {e}'
            job.save()
            raise e
