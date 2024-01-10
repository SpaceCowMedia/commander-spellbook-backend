from unittest import TestCase
from spellbook.admin.utils import auto_fix_missing_braces_to_oracle_symbols


class TestAddCurlyBracketsToOracleSymbols(TestCase):
    def test_empty_string(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(''), '')

    def test_no_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'? *'), r'? *')

    def test_one_oracle_symbol(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'W'), r'{W}')

    def test_one_oracle_symbol_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{W}'), r'{W}')

    def test_multiple_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'WUBRG'), r'{W}{U}{B}{R}{G}')

    def test_multiple_oracle_symbols_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{W}{U}{B}{R}{G}'), r'{W}{U}{B}{R}{G}')

    def test_hybrid_manas(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'2/W'), r'{2/W}')

    def test_hybrid_manas_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{2/W}'), r'{2/W}')

    def test_hybrid_mana_with_multiple_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'2/W/PU12BR/PG'), r'{2/W/P}{U}{12}{B}{R/P}{G}')

    def test_hybrid_mana_with_multiple_symbols_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'11}2/W/PU{12}{B}{1}2R/P{G}'), r'11}2/W/PU{12}{B}{1}2R/P{G}')

    def test_with_following_text(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'WUBRG mana'), r'WUBRG mana')
