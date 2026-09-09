from django.urls import reverse
from spellbook.models import Card
from ..testing import SpellbookTestCaseWithSeeding

# every field the form fills from Scryfall, and the input it writes into
FILLED_FIELDS = [
    'identity', 'type_line', 'faces', 'oracle_text', 'keywords', 'mana_cost', 'power', 'toughness',
    'loyalty', 'layout', 'produced_mana', 'mana_value', 'reserved', 'latest_printing_set', 'reprinted',
    'game_changer', 'spoiler', 'layout_rotation_front',
]


class CardFormScriptTests(SpellbookTestCaseWithSeeding):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.page = self.client.get(reverse('admin:spellbook_card_add')).content.decode()

    def test_the_form_fills_every_field_scryfall_decides(self):
        for field in FILLED_FIELDS:
            with self.subTest(field=field):
                self.assertIn(f"#id_{field}'", self.page)

    def test_it_writes_into_inputs_the_form_actually_renders(self):
        for field in FILLED_FIELDS:
            with self.subTest(field=field):
                self.assertRegex(self.page, rf'id="id_{field}"')

    def test_the_numbers_a_search_compares_are_not_written_by_hand(self):
        # they are derived when the card is saved, so the form shows them without offering them
        for field in ('power_value', 'toughness_value', 'loyalty_value'):
            with self.subTest(field=field):
                self.assertNotIn(f"#id_{field}'", self.page)
                self.assertNotRegex(self.page, rf'<input[^>]*id="id_{field}"')

    def test_the_mana_value_is_written_as_a_whole_number(self):
        # the half mana of the joke cards is the only fractional cost Scryfall reports
        self.assertIn('Math.round(data.cmc)', self.page)

    def test_every_scryfall_field_of_the_model_is_accounted_for(self):
        # images and the fields the tagger decides are filled elsewhere in the same script
        elsewhere = {name for name in Card.scryfall_fields() if name.startswith('image_uri_')}
        elsewhere |= {'tutor', 'mass_land_denial', 'extra_turn', 'color'}
        derived = {'power_value', 'toughness_value', 'loyalty_value'}
        unaccounted = set(Card.scryfall_fields()) - set(FILLED_FIELDS) - elsewhere - derived
        self.assertEqual(unaccounted, set())
        for field in elsewhere - {'tutor', 'mass_land_denial', 'extra_turn', 'color'}:
            with self.subTest(field=field):
                self.assertIn(f"#id_{field}'", self.page)
