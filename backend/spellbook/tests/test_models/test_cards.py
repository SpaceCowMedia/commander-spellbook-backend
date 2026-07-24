from django.test import TestCase
from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from django.core.exceptions import ValidationError
from common.inspection import count_methods
from spellbook.models import Card, CardType
from spellbook.models.scryfall import SCRYFALL_WEBSITE_CARD_SEARCH
from urllib.parse import quote_plus


class CardTests(SpellbookTestCaseWithSeeding):
    def test_card_fields(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.name, 'A A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 2)
        self.assertEqual(c.features.distinct().count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.identity_w)
        self.assertFalse(c.identity_b)
        self.assertEqual(c.color, 'W')
        self.assertTrue(c.color_w)
        self.assertFalse(c.color_b)
        self.assertTrue(c.legal_commander)
        self.assertFalse(c.spoiler)
        self.assertEqual(c.oracle_text, 'x1')
        self.assertEqual(c.keywords, ['keyword1', 'keyword2'])
        self.assertEqual(c.mana_value, 0)
        self.assertFalse(c.reserved)
        self.assertEqual(c.latest_printing_set, '')
        self.assertFalse(c.reprinted)
        self.assertEqual(c.image_uri_front_png, 'http://localhost/x.png')
        self.assertEqual(c.image_uri_back_normal, 'http://localhost/x.jpg')

    def test_query_string(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(f'q=%21%22{quote_plus(c.name)}%22', c.query_string())

    def test_scryfall_link(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, c.scryfall_link())  # type: ignore
        self.assertIn(c.query_string(), c.scryfall_link())  # type: ignore
        self.assertIn('<a', c.scryfall_link())  # type: ignore
        self.assertTrue(c.scryfall_link().startswith('<a'))  # type: ignore
        self.assertTrue(c.scryfall_link(raw=True).startswith('http'))  # type: ignore
        self.assertIn(c.scryfall_link(raw=True), c.scryfall_link(raw=False))  # type: ignore

    def test_is_legendary(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Legendary Creature - Human'
        c.save()
        self.assertTrue(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Legendary Sorcery'
        self.assertTrue(c.is_of_type(CardType.LEGENDARY))
        c.type_line = 'Creature - Human'
        self.assertFalse(c.is_of_type(CardType.LEGENDARY))

    def test_is_creature(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Creature - Human'
        c.save()
        self.assertTrue(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Legendary Creature - Human'
        self.assertTrue(c.is_of_type(CardType.CREATURE))
        c.type_line = 'Legendary Sorcery'
        self.assertFalse(c.is_of_type(CardType.CREATURE))

    def test_is_instant(self):
        c = Card.objects.get(id=self.c2_id)
        self.assertFalse(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Legendary Instant'
        c.save()
        self.assertTrue(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Instant'
        self.assertTrue(c.is_of_type(CardType.INSTANT))
        c.type_line = 'Sorcery'
        self.assertFalse(c.is_of_type(CardType.INSTANT))

    def test_is_sorcery(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertFalse(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Legendary Sorcery'
        c.save()
        self.assertTrue(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Sorcery'
        self.assertTrue(c.is_of_type(CardType.SORCERY))
        c.type_line = 'Instant'
        self.assertFalse(c.is_of_type(CardType.SORCERY))

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 6)

    def test_face_name(self):
        single = Card.objects.create(name='Single Card', type_line='Instant')
        self.assertEqual(single.face_name(None), 'Single Card')
        self.assertEqual(single.face_name(1), 'Single Card')
        self.assertEqual(single.face_name(2), 'Single Card')  # out of range falls back to the whole name
        dfc = Card.objects.create(name='Front Face // Back Face', type_line='Creature // Creature', faces=2)
        self.assertEqual(dfc.face_name(None), 'Front Face // Back Face')
        self.assertEqual(dfc.face_name(1), 'Front Face')
        self.assertEqual(dfc.face_name(2), 'Back Face')
        self.assertEqual(dfc.face_name(3), 'Front Face // Back Face')  # out of range falls back to the whole name

    def test_name_unaccented(self):
        c = Card.objects.create(name='à, è, ì, ò, ù, y, À, È, Ì, Ò, Ù, Y, á, é, í, ó, ú, ý, Á, É, Í, Ó, Ú, Ý, â, ê, î, ô, û, y, Â, Ê, Î, Ô, Û, Y, ä, ë, ï, ö, ü, ÿ, Ä, Ë, Ï, Ö, Ü, Ÿ', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')
        self.assertEqual(c.name_unaccented, ', '.join('aeiouyAEIOUY' * 4))
        c.name = 'àààèèèìììòòòùùù'
        c.save()
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')
        c.name = 'ààèèììòòùù'
        Card.objects.bulk_update([c], ['name', 'name_unaccented'])
        c.refresh_from_db()
        self.assertEqual(c.name_unaccented, 'aaeeiioouu')
        c.delete()
        Card.objects.bulk_create([Card(name='àààèèèìììòòòùùù', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')])
        c = Card.objects.get(name='àààèèèìììòòòùùù')
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')


class IsCommanderTests(TestCase):
    def test_special_named_cards_are_always_commanders(self):
        for name in (
            'Asmoranomardicadaistinaculdacar',
            'Grist, the Hunger Tide',
            'The Grand Calcutron',
            'The Eternity Elevator',
            'Enolc, Perfect Clone',
            'The Faction Dragon',
            'The Magical City, New',
            'The Waffle Restaurant',
            'The Mystery Raceway',
            'The Goblin Sparring Grounds',
        ):
            c = Card(name=name, mana_value=0, legal_commander=False, type_line='Instant', oracle_text='')
            self.assertTrue(c.is_commander)

    def test_card_without_mana_value_is_not_a_commander(self):
        c = Card(name='Random Card', mana_value=0, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        self.assertFalse(c.is_commander)

    def test_card_not_legal_in_commander_is_not_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=False, type_line='Legendary Creature - Human', oracle_text='')
        self.assertFalse(c.is_commander)

    def test_legendary_creature_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        self.assertTrue(c.is_commander)

    def test_legendary_non_creature_is_not_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Legendary Sorcery', oracle_text='')
        self.assertFalse(c.is_commander)

    def test_legendary_spacecraft_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Legendary Spacecraft', oracle_text='')
        self.assertTrue(c.is_commander)

    def test_legendary_vehicle_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Legendary Vehicle', oracle_text='')
        self.assertTrue(c.is_commander)

    def test_non_legendary_vehicle_is_not_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Vehicle', oracle_text='')
        self.assertFalse(c.is_commander)

    def test_background_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Background', oracle_text='')
        self.assertTrue(c.is_commander)

    def test_second_face_legendary_creature_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Instant // Legendary Creature - Human', oracle_text='')
        self.assertTrue(c.is_commander)

    def test_oracle_text_granting_commander_status_is_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Creature - Human', oracle_text='This creature can be your commander.')
        self.assertTrue(c.is_commander)

    def test_plain_creature_is_not_a_commander(self):
        c = Card(name='Random Card', mana_value=3, legal_commander=True, type_line='Creature - Human', oracle_text='')
        self.assertFalse(c.is_commander)


class KeywordsFieldTests(TestCase):
    def test_new_card_with_empty_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001')
        c.save()

    def test_new_card_with_some_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001', keywords=['A', 'B'])
        c.save()

    def test_new_card_with_wrong_keywords(self):
        c = Card(name='A', oracle_id='00000000-0000-0000-0000-000000000001', keywords=[{}, 1])
        c.save()
        self.assertRaises(ValidationError, lambda: c.full_clean())
