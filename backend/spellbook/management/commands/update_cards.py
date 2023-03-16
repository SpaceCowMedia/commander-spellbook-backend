import traceback
import datetime
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from spellbook.models import Job, Card
from spellbook.variants.list_utils import merge_identities
from ..scryfall import scryfall


class Command(BaseCommand):
    help = 'Updates cards using Scryfall bulk data'

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        job.message += message + '\n'
        job.save()

    def handle(self, *args, **options):
        job = Job.start('update_cards_data', timezone.timedelta(minutes=2))
        if job is None:
            self.stdout.write(self.style.ERROR('Job already running'))
            return
        job.save()
        try:
            self.log_job(job, 'Fetching scryfall dataset...')
            scryfall_name_db = scryfall()
            scryfall_db = {card_object['oracle_id']: card_object for card_object in scryfall_name_db.values()}
            self.log_job(job, 'Fetching scryfall dataset...done')
            self.log_job(job, 'Updating cards...')
            cards_to_update = Card.objects.all()
            updated_count = 0
            for card in cards_to_update:
                updated = False
                if card.oracle_id is None:
                    self.log_job(job, f'Card {card.name} lacks an oracle_id: attempting to find it by name...')
                    card_name = card.name.lower().strip(' \t\n\r')
                    if card_name in scryfall_name_db:
                        card.oracle_id = uuid.UUID(hex=scryfall_name_db[card_name]['oracle_id'])
                        updated = True
                        self.log_job(job, f'Card {card.name} found in scryfall dataset, oracle_id set to {card.oracle_id}')
                    else:
                        self.log_job(job, f'Card {card.name} not found in scryfall dataset', self.style.WARNING)
                        continue
                oracle_id = str(card.oracle_id)
                if oracle_id in scryfall_db:
                    card_in_db = scryfall_db[oracle_id]
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
                        updated_count += 1
                else:
                    self.log_job(job, f'Card {card.name} with oracle id {oracle_id} not found in scryfall dataset', self.style.WARNING)
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            self.log_job(job, 'Updating cards...done', self.style.SUCCESS)
            self.log_job(job, f'Successfully updated {updated_count} cards' if updated_count > 0 else 'Everything is up to date', self.style.SUCCESS)
            job.save()
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Error while updating cards: {e}'
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = message
            job.save()
