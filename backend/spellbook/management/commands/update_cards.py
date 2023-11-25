import traceback
from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone
from spellbook.models import Job, Card, Variant
from spellbook.utils import log_into_job
from ..scryfall import scryfall, update_cards


class Command(BaseCommand):
    help = 'Updates cards using Scryfall bulk data'

    def log_job(self, job, message, style=lambda x: x):
        self.stdout.write(style(message))
        log_into_job(job, message)

    def add_arguments(self, parser: CommandParser):
        parser.add_argument(
            '--force',
            dest='force',
            action='store_true',
        )

    def handle(self, *args, **options):
        job = Job.start('update_cards')
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
            updated_cards_count = len(cards_to_save)
            updated_variants_count = 0
            Card.objects.bulk_update(cards_to_save, fields=['name', 'name_unaccented', 'oracle_id', 'identity', 'spoiler', 'oracle_text', 'type_line', 'latest_printing_set', 'reprinted'] + Card.legalities_fields() + Card.prices_fields())
            self.log_job(job, 'Updating cards...done', self.style.SUCCESS)
            if updated_cards_count > 0 or options['force']:
                self.log_job(job, 'Updating variants...')
                variants_query = Variant.objects.prefetch_related('uses', 'cardinvariant_set', 'templateinvariant_set')
                if not options['force']:
                    variants_query = variants_query.filter(uses__in=cards_to_save)
                else:
                    self.log_job(job, 'Forced update of all variants')
                variants = list(variants_query)
                variants_to_save = []
                for variant in variants:
                    requires_commander = any(civ.must_be_commander for civ in variant.cardinvariant_set.all()) \
                        or any(tiv.must_be_commander for tiv in variant.templateinvariant_set.all())
                    if variant.update(variant.uses.all(), requires_commander):
                        variants_to_save.append(variant)
                updated_variants_count = len(variants_to_save)
                Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields())
                self.log_job(job, 'Updating variants...done', self.style.SUCCESS)
            job.termination = timezone.now()
            job.status = Job.Status.SUCCESS
            if updated_cards_count > 0 or updated_variants_count > 0:
                self.log_job(job, f'Successfully updated {updated_cards_count} cards and {updated_variants_count} variants', self.style.SUCCESS)
            else:
                self.log_job(job, 'No cards to update', self.style.SUCCESS)
            job.save()
        except Exception as e:
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            message = f'Error while updating cards: {e}'
            job.termination = timezone.now()
            job.status = Job.Status.FAILURE
            job.message = message
            job.save()
