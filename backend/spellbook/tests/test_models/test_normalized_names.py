from django.test import SimpleTestCase
from spellbook.models import strip_accents


class StripAccentsTests(SimpleTestCase):
    def test_it_takes_the_accents_off(self):
        self.assertEqual(strip_accents('Jötun Grunt'), 'Jotun Grunt')
        self.assertEqual(strip_accents('Márton Stromgald'), 'Marton Stromgald')
        self.assertEqual(strip_accents('Ætherling'), 'Aetherling')

    def test_it_spells_out_a_letter_that_carries_no_accent_to_take_off(self):
        # nothing here decomposes, so the decomposition alone would leave every one of them as it is
        self.assertEqual(strip_accents('Æther Vial'), 'Aether Vial')
        self.assertEqual(strip_accents('æther'), 'aether'),
        self.assertEqual(strip_accents('Œuvre'), 'Oeuvre')
        self.assertEqual(strip_accents('Straße'), 'Strasse')
        self.assertEqual(strip_accents('Øresund'), 'Oresund')

    def test_it_writes_punctuation_the_way_a_keyboard_does(self):
        self.assertEqual(strip_accents('Human—Time Lord Meta-Crisis'), 'Human-Time Lord Meta-Crisis')
        self.assertEqual(strip_accents('Ratonhnhaké꞉ton'), 'Ratonhnhaketon')
        self.assertEqual(strip_accents('Wizards of the Coast® Customer Service'), 'Wizards of the Coast Customer Service')

    def test_a_name_a_keyboard_already_writes_is_left_alone(self):
        for name in ('Lightning Bolt', "Ach! Hans, Run!", 'Fire // Ice', 'B.F.M. (Big Furry Monster)'):
            with self.subTest(name=name):
                self.assertEqual(strip_accents(name), name)

    def test_it_leaves_nothing_outside_ascii_in_a_card_name(self):
        for name in ('Æther Vial', 'Jötun Grunt', 'Ratonhnhaké꞉ton', 'Human—Time Lord Meta-Crisis'):
            with self.subTest(name=name):
                self.assertTrue(strip_accents(name).isascii())
