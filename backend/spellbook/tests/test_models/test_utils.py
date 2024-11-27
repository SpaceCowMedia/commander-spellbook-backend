from django.test import TestCase
from spellbook.models import merge_identities
from spellbook.models.utils import auto_fix_missing_braces_to_oracle_symbols, upper_oracle_symbols, sanitize_mana, sanitize_scryfall_query


class TestAddCurlyBracketsToOracleSymbols(TestCase):
    def test_empty_string(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(''), '')

    def test_no_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'? *'), r'? *')

    def test_one_oracle_symbol(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'W'), r'{W}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'w'), r'{w}')

    def test_one_oracle_symbol_with_curly_brackets(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{W}'), r'{W}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'{w}'), r'{w}')

    def test_multiple_oracle_symbols(self):
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'WUBRG'), r'{W}{U}{B}{R}{G}')
        self.assertEqual(auto_fix_missing_braces_to_oracle_symbols(r'wubrg'), r'{w}{u}{b}{r}{g}')

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


class TestUpperOracleSymbols(TestCase):
    def test_empty_string(self):
        self.assertEqual(upper_oracle_symbols(''), '')

    def test_no_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'aaa eee oo u ? *'), r'aaa eee oo u ? *')

    def test_one_oracle_symbol(self):
        self.assertEqual(upper_oracle_symbols(r'{w}'), r'{W}')

    def test_multiple_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'{w}{u}{b}{r}{g}'), r'{W}{U}{B}{R}{G}')

    def test_mixed_case_oracle_symbols(self):
        self.assertEqual(upper_oracle_symbols(r'{W}{u}{b}{R}{g}'), r'{W}{U}{B}{R}{G}')

    def test_hybrid_mana(self):
        self.assertEqual(upper_oracle_symbols(r'{2/w}'), r'{2/W}')

    def test_free_text(self):
        self.assertEqual(upper_oracle_symbols(r'ahm {w} yes u {2/w} r bg {2} {b/p} b/p'), r'ahm {W} yes u {2/W} r bg {2} {B/P} b/p')


class TestSanitizeMana(TestCase):
    def test_empty_string(self):
        self.assertEqual(sanitize_mana(''), '')

    def test_no_mana(self):
        self.assertEqual(sanitize_mana('aaa eee oo ? *'), 'aaa eee oo ? *')

    def test_one_mana(self):
        self.assertEqual(sanitize_mana('{w}'), '{W}')
        self.assertEqual(sanitize_mana('w'), '{W}')
        self.assertEqual(sanitize_mana('c'), '{C}')

    def test_multiple_mana(self):
        self.assertEqual(sanitize_mana('{w}{u}{b}{r}{g}{b/p}'), '{W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_mana('wubrgb/p'), '{W}{U}{B}{R}{G}{B/P}')

    def test_add_braces(self):
        self.assertEqual(sanitize_mana('W'), '{W}')
        self.assertEqual(sanitize_mana('WU'), '{W}{U}')
        self.assertEqual(sanitize_mana('w'), '{W}')
        self.assertEqual(sanitize_mana('wu'), '{W}{U}')

    def test_fix_phyrexian(self):
        self.assertEqual(sanitize_mana('WP'), '{W}{P}')
        self.assertEqual(sanitize_mana('W/P'), '{W/P}')
        self.assertEqual(sanitize_mana('{WP}'), '{W/P}')
        self.assertEqual(sanitize_mana('{wp}'), '{W/P}')

    def test_fix_hybrid(self):
        self.assertEqual(sanitize_mana('2/W'), '{2/W}')
        self.assertEqual(sanitize_mana('2/W/PU12BR/PG'), '{2/W/P}{U}{12}{B}{R/P}{G}')
        self.assertEqual(sanitize_mana('{W/G}'), '{G/W}')
        self.assertEqual(sanitize_mana('{W/G}{U}'), '{G/W}{U}')
        self.assertEqual(sanitize_mana('{R/B}'), '{B/R}')
        self.assertEqual(sanitize_mana('W/G'), '{G/W}')
        self.assertEqual(sanitize_mana('W/GU'), '{G/W}{U}')
        self.assertEqual(sanitize_mana('{W/2}'), '{2/W}')
        self.assertEqual(sanitize_mana('W/2'), '{2/W}')
        self.assertEqual(sanitize_mana('P/R'), '{R/P}')


class TestSanitizeScryfallQuery(TestCase):
    def test_empty_string(self):
        self.assertEqual(sanitize_scryfall_query(''), '')

    def test_no_parameters(self):
        self.assertEqual(sanitize_scryfall_query('aaa eee oo ? *'), 'aaa eee oo ? *')

    def test_mana_parameters(self):
        self.assertEqual(sanitize_scryfall_query('mana={w}'), 'mana={W}')
        self.assertEqual(sanitize_scryfall_query('tou:5   mana={w}   pow:2'), 'tou:5   mana={W}   pow:2')
        self.assertEqual(sanitize_scryfall_query('mana=w'), 'mana={W}')
        self.assertEqual(sanitize_scryfall_query('mana=c'), 'mana={C}')
        self.assertEqual(sanitize_scryfall_query('mana={w}{u}{b}{r}{g}{b/p}'), 'mana={W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_scryfall_query('mana=wubrgb/p'), 'mana={W}{U}{B}{R}{G}{B/P}')
        self.assertEqual(sanitize_scryfall_query('mana=WU'), 'mana={W}{U}')
        self.assertEqual(sanitize_scryfall_query('mana=wu'), 'mana={W}{U}')
        self.assertEqual(sanitize_scryfall_query('mana={WP}'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={wp}'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana=WP'), 'mana={W}{P}')
        self.assertEqual(sanitize_scryfall_query('mana=W/P'), 'mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('a mana={WP}'), 'a mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b'), 'mana={W/P} b')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP}'), 'mana={W/P} b mana={W/P}')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c'), 'mana={W/P} b mana={W/P} c')
        self.assertEqual(sanitize_scryfall_query('-mana:{w} -mana:{u} -mana:{b} -mana:{r} -mana:{g} -mana:{b/p}'), '-mana:{W} -mana:{U} -mana:{B} -mana:{R} -mana:{G} -mana:{B/P}')

    def test_removal_of_format(self):
        self.assertEqual(sanitize_scryfall_query('format:standard'), '')
        self.assertEqual(sanitize_scryfall_query('format:modern'), '')
        self.assertEqual(sanitize_scryfall_query('tou>5 format:edh format:commander'), 'tou>5')
        self.assertEqual(sanitize_scryfall_query('legal:standard f:modern'), '')
        self.assertEqual(sanitize_scryfall_query('-legal:edh tou=3 format:commander'), 'tou=3')
        self.assertEqual(sanitize_scryfall_query('pow:2   format:standard      tou:5'), 'pow:2      tou:5')
        self.assertEqual(sanitize_scryfall_query('f:brawl   format:standard      tou:5'), 'tou:5')
        self.assertEqual(sanitize_scryfall_query('pow:2   format:standard      f:edh'), 'pow:2')
        self.assertEqual(sanitize_scryfall_query('format:vintage   format:standard      legal:brawl'), '')

    def test_combined_transform(self):
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c format:modern'), 'mana={W/P} b mana={W/P} c')
        self.assertEqual(sanitize_scryfall_query('mana={WP} b mana={WP} c format:modern f:edh'), 'mana={W/P} b mana={W/P} c')


class UtilsTests(TestCase):
    def test_merge_identities(self):
        self.assertEqual(merge_identities(['', '']), 'C')
        for c in 'CWUBRG':
            self.assertEqual(merge_identities([c, '']), c)
            self.assertEqual(merge_identities(['', c]), c)
            self.assertEqual(merge_identities([c, c]), c)
        self.assertSetEqual(set(merge_identities(['W', 'U'])), set('WU'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B'])), set('WUB'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R'])), set('WUBR'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R', 'G'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(sorted(['W', 'U', 'B', 'R', 'G']))), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['W', 'U', 'B', 'R', 'G', 'W'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['WU', 'BR', 'G', 'WG'])), set('WUBRG'))
        self.assertSetEqual(set(merge_identities(['S'])), set('C'))
        self.assertSetEqual(set(merge_identities(['S', 'R'])), set('R'))
        self.assertSetEqual(set(merge_identities(['r', 'g'])), set('RG'))
        self.assertSetEqual(set(merge_identities(['g', 'r'])), set('RG'))
