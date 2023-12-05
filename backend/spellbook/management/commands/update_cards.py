from django.core.management.base import CommandParser
from spellbook.models import Card, Variant
from ..abstract_command import AbstractCommand
from ..scryfall import scryfall, update_cards


class Command(AbstractCommand):
    name = 'update_cards'
    help = 'Updates cards using Scryfall bulk data'

    def add_arguments(self, parser: CommandParser):
        super().add_arguments(parser)
        parser.add_argument(
            '--force',
            dest='force',
            action='store_true',
        )

    def run(self, *args, **options):
        self.log('Fetching Scryfall and EDHREC datasets...')
        scryfall_name_db = scryfall()
        self.log('Fetching Scryfall and EDHREC datasets...done')
        self.log('Updating cards...')
        cards_to_update = list(Card.objects.all())
        cards_to_save = update_cards(
            cards_to_update,
            scryfall_name_db,
            log=lambda x: self.log(x),
            log_warning=lambda x: self.log(x, self.style.WARNING),
            log_error=lambda x: self.log(x, self.style.ERROR),
        )
        updated_cards_count = len(cards_to_save)
        updated_variants_count = 0
        Card.objects.bulk_update(cards_to_save, fields=['name', 'name_unaccented', 'oracle_id', 'identity', 'spoiler', 'oracle_text', 'type_line', 'latest_printing_set', 'reprinted'] + Card.legalities_fields() + Card.prices_fields())
        self.log('Updating cards...done', self.style.SUCCESS)
        if updated_cards_count > 0 or options['force']:
            self.log('Updating variants...')
            variants_query = Variant.objects.prefetch_related('uses', 'cardinvariant_set', 'templateinvariant_set')
            if not options['force']:
                variants_query = variants_query.filter(uses__in=cards_to_save)
            else:
                self.log('Forced update of all variants')
            variants = list(variants_query)
            variants_to_save = []
            for variant in variants:
                requires_commander = any(civ.must_be_commander for civ in variant.cardinvariant_set.all()) \
                    or any(tiv.must_be_commander for tiv in variant.templateinvariant_set.all())
                if variant.update(variant.uses.all(), requires_commander):
                    variants_to_save.append(variant)
            updated_variants_count = len(variants_to_save)
            Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields(), batch_size=5000)
            self.log('Updating variants...done', self.style.SUCCESS)
        if updated_cards_count > 0 or updated_variants_count > 0:
            self.log(f'Successfully updated {updated_cards_count} cards and {updated_variants_count} variants', self.style.SUCCESS)
        else:
            self.log('No cards to update', self.style.SUCCESS)
