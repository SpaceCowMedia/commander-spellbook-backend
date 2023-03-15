import traceback
from ..scryfall import scryfall
from django.core.management.base import BaseCommand
from spellbook.models import Job, Card
from spellbook.variants.list_utils import merge_identities
from django.utils import timezone
import datetime


class Command(BaseCommand):
    help = 'Updates cards using Scryfall bulk data'

    def handle(self, *args, **options):
        job = Job.start('update_cards_data', timezone.timedelta(minutes=2))
        if job is None:
            self.stdout.write(self.style.ERROR('Job already running'))
            return
        job.save()
        try:
            self.stdout.write('Fetching scryfall dataset...')
            scryfall_db = {card_object['oracle_id']: card_object for _, card_object in scryfall().items()}
            self.stdout.write('Fetching scryfall dataset...done')
            self.stdout.write('Updating cards...')
            cards_to_update = Card.objects.filter(oracle_id__isnull=False)
            updated_count = cards_to_update.count()
            for card in cards_to_update:
                oracle_id = str(card.oracle_id)
                if oracle_id in scryfall_db:
                    card_in_db = scryfall_db[oracle_id]
                    updated = False
                    card_name = card_in_db['name']
                    if card.name != card_name:
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
                    if updated:
                        card.save()
                else:
                    self.stdout.write(self.style.WARNING(f'Card {card.name} not found in Scryfall, using oracle id {oracle_id}'))
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            job.message = f'Successfully updated {updated_count} cards'
            job.save()
            self.stdout.write('Updating cards...done')
            self.stdout.write(self.style.SUCCESS(job.message))
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Error while updating cards: {e}'
            job.termination = timezone.now()
            job.status = Job.Status.ERROR
            job.message = message
            job.save()
