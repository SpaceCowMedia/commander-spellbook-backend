from unittest import TestCase
from rest_framework.serializers import ListSerializer
from common.serializers import DeckSerializer
from common.abstractions import Deck


class TestDeckSerializer(TestCase):
    def test_empty_dict(self):
        serializer = DeckSerializer(data={'main': [], 'commanders': []})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        deck: Deck = serializer.save()  # type: ignore
        self.assertEqual(deck.main, [])
        self.assertEqual(deck.commanders, [])

    def test_empty_string(self):
        serializer = DeckSerializer(data='')
        self.assertTrue(serializer.is_valid(), serializer.errors)
        deck: Deck = serializer.save()  # type: ignore
        self.assertEqual(deck.main, [])
        self.assertEqual(deck.commanders, [])

    def common_assertions(self, serializer: DeckSerializer | ListSerializer):
        self.assertTrue(serializer.is_valid(), serializer.errors)
        deck: Deck = serializer.save()  # type: ignore
        self.assertEqual(len(deck.main), 3)
        self.assertEqual(deck.main[0].card, 'Forest')
        self.assertEqual(deck.main[0].quantity, 10)
        self.assertEqual(deck.main[1].card, 'Llanowar Elves')
        self.assertEqual(deck.main[1].quantity, 4)
        self.assertEqual(deck.main[2].card, 'Bottomless Pool // Locker Room')
        self.assertEqual(deck.main[2].quantity, 1)
        self.assertEqual(len(deck.commanders), 1)
        self.assertEqual(deck.commanders[0].card, 'Nissa, Who Shakes the World')
        self.assertEqual(deck.commanders[0].quantity, 1)

    def test_dict(self):
        serializer = DeckSerializer(data={
            'main': [
                {'card': 'Forest', 'quantity': 10},
                {'card': 'Llanowar Elves', 'quantity': 4},
                {'card': 'Bottomless Pool // Locker Room', 'quantity': 1},
            ],
            'commanders': [
                {'card': 'Nissa, Who Shakes the World', 'quantity': 1},
            ],
        })
        self.common_assertions(serializer)

    def test_simple_string(self):
        serializer = DeckSerializer(data='''
        10 Forest
        4 Llanowar Elves
        Bottomless Pool // Locker Room
        // Commanders
        1 Nissa, Who Shakes the World
        '''.replace('        ', ''))
        self.common_assertions(serializer)

    def test_moxfield_string(self):
        serializer = DeckSerializer(data='''
        10 Forest (M21) 123
        4 Llanowar Elves (M19) 234p
        1 Bottomless Pool // Locker Room (IKO) 345s
        // Command Zone
        1 Nissa, Who Shakes the World (PGRN) UMA-345 *F*
        '''.replace('        ', ''))
        self.common_assertions(serializer)

    def test_deckstats_string(self):
        for commander_tag in ('#!Commander', '# !Commander'):
            with self.subTest(commander_tag=commander_tag):
                serializer = DeckSerializer(data=f'''
                10 Forest
                4 Llanowar Elves
                1 Bottomless Pool // Locker Room
                // Commanders
                1 Nissa, Who Shakes the World {commander_tag}
                '''.replace('        ', ''))
                self.common_assertions(serializer)

    def test_archidekt_string(self):
        serializer = DeckSerializer(data='''
        10x Forest (clb) 662 [Lands] ^BID,#fbe955^
        4x Llanowar Elves (m19) 192 [Creatures] ^COMPILED,#ef56e4^
        1x Bottomless Pool // Locker Room (iko) 243 [ASD,KEK] ^COMPILED,#ef56e4^
        1x Nissa, Who Shakes the World () 30 [Commander{top}] ^Have,#37d67a^
        '''.replace('        ', ''))
        self.common_assertions(serializer)

    def test_archidekt_string_with_sections(self):
        serializer = DeckSerializer(data='''
        Commander
        1x Nissa, Who Shakes the World (pgrn) 30 [Commander{top}] ^Have,#37d67a^
        Mainboard
        10x Forest (clb) 662 [Lands] ^BID,#fbe955^
        4x Llanowar Elves (m19) 192 [Creatures] ^COMPILED,#ef56e4^
        1x Bottomless Pool // Locker Room (iko) 243 [ASD,KEK] ^COMPILED,#ef56e4^
        Maybeboard
        2x Island (m21) 189 [Lands] ^BID,#fbe955^
        Sideboard
        3x Swamp (m21) 190 [Lands] ^BID,#fbe955^
        '''.replace('        ', ''))
        self.common_assertions(serializer)

    def test_tapped_out_string(self):
        serializer = DeckSerializer(data='''
        About
        Name My Deck

        Commander
        1x Nissa, Who Shakes the World (DAR) 198

        Deck
        10x Forest (M21) 123
        4x Llanowar Elves (M19) 234
        1x Bottomless Pool // Locker Room (IKO) 345

        Sideboard
        2x Island (M21) 189
        3x Swamp (M21) 190
        '''.replace('        ', ''))
        self.common_assertions(serializer)

    def test_too_many_commanders(self):
        serializer = DeckSerializer(data=f'''
        // Main
        10 Forest
        // Commanders
        {"\n".join(f"1 Pinocchio #{i}" for i in range(DeckSerializer.MAX_COMMANDERS_LIST_LENGTH + 1))}
        ''')
        self.assertFalse(serializer.is_valid())
        self.assertIn('commanders', serializer.errors)
        self.assertNotIn('main', serializer.errors)

    def test_too_many_main_deck_cards(self):
        serializer = DeckSerializer(data=f'''
        // Main
        {"\n".join(f"1 Pinocchio #{i}" for i in range(DeckSerializer.MAX_MAIN_LIST_LENGTH + 1))}
        // Commanders
        1 Nissa, Who Shakes the World
        ''')
        self.assertFalse(serializer.is_valid())
        self.assertIn('main', serializer.errors)
        self.assertNotIn('commanders', serializer.errors)
