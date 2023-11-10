import traceback
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from spellbook.models import Job, Card
from ..scryfall import scryfall, update_cards


class Command(BaseCommand):
    help = 'Updates cards using Scryfall bulk data'

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        job.message += message + '\n'
        job.save()

    def handle(self, *args, **options):
        job = Job.start('update_cards_data')
        if job is None:
            self.stdout.write(self.style.ERROR('Job already running'))
            return
        job.save()
        try:
            self.log_job(job, 'Fetching Scryfall and EDHREC datasets...')
            scryfall_name_db = scryfall()
            self.log_job(job, 'Fetching Scryfall and EDHREC datasets...done')
            self.log_job(job, 'Updating cards...')
            cards_to_update = list(Card.objects.all())
            cards_to_save = update_cards(
                cards_to_update,
                scryfall_name_db,
                lambda x: self.log_job(job, x),
                lambda x: self.log_job(job, x, self.style.WARNING),
                lambda x: self.log_job(job, x, self.style.ERROR),
            )
            updated_count = len(cards_to_save)
            if updated_count > 0:
                with transaction.atomic(durable=True):
                    # TODO: Update variants
                    Card.objects.bulk_update(cards_to_save, fields=['name', 'name_unaccented', 'oracle_id', 'identity', 'spoiler', 'oracle_text', 'type_line'] + Card.legalities_fields() + Card.prices_fields())
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
