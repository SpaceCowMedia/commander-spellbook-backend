from django.test import TestCase
from spellbook.models.validators import *

class TestValidators(TestCase):
    def test_mana_symbol(self):
        self.assertRegexpMatches('W', MANA_SYMBOL)
        self.assertRegexpMatches('U', MANA_SYMBOL)
        self.assertRegexpMatches('B', MANA_SYMBOL)
        self.assertRegexpMatches('R', MANA_SYMBOL)
        self.assertRegexpMatches('G', MANA_SYMBOL)
        self.assertRegexpMatches('C', MANA_SYMBOL)
        self.assertRegexpMatches('P', MANA_SYMBOL)
        self.assertRegexpMatches('W/P', MANA_SYMBOL)
        self.assertRegexpMatches('U/P', MANA_SYMBOL)
        self.assertRegexpMatches('B/P', MANA_SYMBOL)
        self.assertRegexpMatches('R/P', MANA_SYMBOL)
        self.assertRegexpMatches('G/P', MANA_SYMBOL)
        self.assertRegexpMatches('W/U', MANA_SYMBOL)
        self.assertRegexpMatches('W/B', MANA_SYMBOL)
        self.assertRegexpMatches('U/B', MANA_SYMBOL)
        self.assertRegexpMatches('U/R', MANA_SYMBOL)
        self.assertRegexpMatches('B/R', MANA_SYMBOL)
        self.assertRegexpMatches('B/G', MANA_SYMBOL)
        self.assertRegexpMatches('R/G', MANA_SYMBOL)
        self.assertRegexpMatches('0', MANA_SYMBOL)
        self.assertRegexpMatches('1', MANA_SYMBOL)
        self.assertRegexpMatches('2', MANA_SYMBOL)
        self.assertRegexpMatches('3', MANA_SYMBOL)
        self.assertRegexpMatches('4', MANA_SYMBOL)
        self.assertRegexpMatches('5', MANA_SYMBOL)
        self.assertRegexpMatches('16', MANA_SYMBOL)
        self.assertRegexpMatches('X', MANA_SYMBOL)
        self.assertRegexpMatches('Y', MANA_SYMBOL)
        self.assertRegexpMatches('Z', MANA_SYMBOL)
        self.assertRegexpMatches('S', MANA_SYMBOL)
        self.assertRegexpMatches('W/U/P', MANA_SYMBOL)
        self.assertRegexpMatches('W/B/P', MANA_SYMBOL)
        self.assertRegexpMatches('U/B/P', MANA_SYMBOL)
        self.assertRegexpMatches('U/R/P', MANA_SYMBOL)
        self.assertRegexpMatches('B/R/P', MANA_SYMBOL)
        self.assertRegexpMatches('B/G/P', MANA_SYMBOL)
        self.assertRegexpMatches('R/G/P', MANA_SYMBOL)

    def test_mana_regex(self):
        self.assertRegexpMatches('{W}', MANA_REGEX)
        self.assertRegexpMatches('{U}', MANA_REGEX)
        self.assertRegexpMatches('{B}', MANA_REGEX)
        self.assertRegexpMatches('{R}', MANA_REGEX)
        self.assertRegexpMatches('{G}', MANA_REGEX)
        self.assertRegexpMatches('{C}', MANA_REGEX)
        self.assertRegexpMatches('{P}{2}{P}', MANA_REGEX)
        self.assertRegexpMatches('{W/P}', MANA_REGEX)
        self.assertRegexpMatches('{U/P}', MANA_REGEX)
        self.assertRegexpMatches('{B/P}', MANA_REGEX)
        self.assertRegexpMatches('{R/P}', MANA_REGEX)
        self.assertRegexpMatches('{G/P}', MANA_REGEX)
        self.assertRegexpMatches('{W/U}', MANA_REGEX)
        self.assertRegexpMatches('{W/B}', MANA_REGEX)
        self.assertRegexpMatches('{U/B}', MANA_REGEX)
        self.assertRegexpMatches('{U/R}', MANA_REGEX)
        self.assertRegexpMatches('{B/R}', MANA_REGEX)
        self.assertRegexpMatches('{B/G}', MANA_REGEX)
        self.assertRegexpMatches('{R/G}', MANA_REGEX)
        self.assertRegexpMatches('{0}', MANA_REGEX)
        self.assertRegexpMatches('{1}', MANA_REGEX)
        self.assertRegexpMatches('{2}', MANA_REGEX)
        self.assertRegexpMatches('{3}', MANA_REGEX)
        self.assertRegexpMatches('{4}', MANA_REGEX)
        self.assertRegexpMatches('{5}', MANA_REGEX)
        self.assertRegexpMatches('{16}', MANA_REGEX)
        self.assertRegexpMatches('{X}', MANA_REGEX)
        self.assertRegexpMatches('{Y}', MANA_REGEX)
        self.assertRegexpMatches('{Z}', MANA_REGEX)
        self.assertRegexpMatches('{S}', MANA_REGEX)
        self.assertRegexpMatches('{W/U/P}', MANA_REGEX)
        self.assertRegexpMatches('{W/B/P}', MANA_REGEX)
        self.assertRegexpMatches('{U/B/P}', MANA_REGEX)
        self.assertRegexpMatches('{U/R/P}', MANA_REGEX)
        self.assertRegexpMatches('{B/R/P}', MANA_REGEX)
        self.assertRegexpMatches('{B/G/P}', MANA_REGEX)
        self.assertRegexpMatches('{R/G/P}{W}', MANA_REGEX)
        self.assertRegexpMatches('{R/G/P}{C} and {W}', MANA_REGEX)
        self.assertRegexpMatches('{W}{W}{U}{U} each turn.', MANA_REGEX)
        self.assertNotRegexpMatches('[R/G/P]', MANA_REGEX)
        self.assertNotRegexpMatches('{R} and }U}', MANA_REGEX)

    def test_double_square_bracket_text(self):
        pass  # TODO: Implement

    def test_oracle_symbol(self):
        pass  # TODO: Implement

    def test_symbols_text(self):
        pass  # TODO: Implement

    def test_identity(self):
        pass  # TODO: Implement

    def test_scryfall_query(self):
        pass  # TODO: Implement
