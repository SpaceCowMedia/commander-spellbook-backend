from django.db.models import Q, Count
from spellbook.models import Card
from spellbook.models.variant import Variant
from ..abstract_command import AbstractCommand
from ..scryfall import scryfall, update_cards


class Command(AbstractCommand):
    name = 'update_cards'
    help = 'Updates cards using Scryfall/EDHREC bulk data'
    batch_size = 5000

    def run(self, *args, **options):
        self.log('Fetching Scryfall and EDHREC datasets...')
        scryfall_name_db = scryfall()
        self.log('Fetching Scryfall and EDHREC datasets...done')
        self.log('Updating cards...')
        cards_to_update = list(Card.objects.all())
        cards_count: dict[int, int] = {
            i: c
            for i, c in Card.objects.annotate(
                updated_variant_count=Count('used_in_variants', distinct=True, filter=Q(used_in_variants__status__in=Variant.public_statuses())),
            ).values_list('id', 'updated_variant_count')
        }
        cards_to_save = update_cards(
            cards_to_update,
            scryfall_name_db,
            cards_count,
            log=lambda x: self.log(x),
            log_warning=lambda x: self.log(x, self.style.WARNING),
            log_error=lambda x: self.log(x, self.style.ERROR),
        )
        updated_card_count = len(cards_to_save)
        Card.objects.bulk_update(cards_to_save, fields=['name', 'name_unaccented', 'oracle_id', 'variant_count'] + Card.scryfall_fields() + Card.playable_fields(), batch_size=self.batch_size)
        self.log('Updating cards...done', self.style.SUCCESS)
        if updated_card_count > 0:
            self.log(f'Successfully updated {updated_card_count} cards', self.style.SUCCESS)
        else:
            self.log('No cards to update', self.style.SUCCESS)
