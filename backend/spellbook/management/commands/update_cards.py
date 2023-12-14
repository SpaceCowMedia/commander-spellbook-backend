from spellbook.models import Card
from ..abstract_command import AbstractCommand
from ..scryfall import scryfall, update_cards


class Command(AbstractCommand):
    name = 'update_cards'
    help = 'Updates cards using Scryfall/EDHREC bulk data'

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
        Card.objects.bulk_update(cards_to_save, fields=['name', 'name_unaccented', 'oracle_id', 'identity', 'spoiler', 'oracle_text', 'type_line', 'latest_printing_set', 'reprinted'] + Card.legalities_fields() + Card.prices_fields())
        self.log('Updating cards...done', self.style.SUCCESS)
        if updated_cards_count > 0:
            self.log(f'Successfully updated {updated_cards_count} cards', self.style.SUCCESS)
        else:
            self.log('No cards to update', self.style.SUCCESS)
