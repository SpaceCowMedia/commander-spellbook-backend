from django.test import TestCase
from spellbook.models.validators import MANA_SYMBOL, MANA_REGEX, ORACLE_SYMBOL, DOUBLE_SQUARE_BRACKET_TEXT_REGEX, SYMBOLS_TEXT_REGEX, SCRYFALL_QUERY_REGEX


class TestValidators(TestCase):
    def test_mana_symbol(self):
        regex = f'^{MANA_SYMBOL}$'
        self.assertRegex('W', regex)
        self.assertRegex('U', regex)
        self.assertRegex('B', regex)
        self.assertRegex('R', regex)
        self.assertRegex('G', regex)
        self.assertRegex('C', regex)
        self.assertRegex('P', regex)
        self.assertRegex('W/P', regex)
        self.assertRegex('U/P', regex)
        self.assertRegex('B/P', regex)
        self.assertRegex('R/P', regex)
        self.assertRegex('G/P', regex)
        self.assertRegex('W/U', regex)
        self.assertRegex('W/B', regex)
        self.assertRegex('U/B', regex)
        self.assertRegex('U/R', regex)
        self.assertRegex('B/R', regex)
        self.assertRegex('B/G', regex)
        self.assertRegex('R/G', regex)
        self.assertRegex('0', regex)
        self.assertRegex('1', regex)
        self.assertRegex('2', regex)
        self.assertRegex('3', regex)
        self.assertRegex('4', regex)
        self.assertRegex('5', regex)
        self.assertRegex('16', regex)
        self.assertRegex('X', regex)
        self.assertRegex('Y', regex)
        self.assertRegex('Z', regex)
        self.assertRegex('S', regex)
        self.assertRegex('W/U/P', regex)
        self.assertRegex('W/B/P', regex)
        self.assertRegex('U/B/P', regex)
        self.assertRegex('U/R/P', regex)
        self.assertRegex('B/R/P', regex)
        self.assertRegex('B/G/P', regex)
        self.assertRegex('R/G/P', regex)
        self.assertNotRegex('R/G/P}', regex)
        self.assertNotRegex('{R/G/P}', regex)
        self.assertNotRegex('R/G/P{', regex)
        self.assertNotRegex('J', regex)
        self.assertNotRegex('T', regex)
        self.assertNotRegex('Q', regex)
        self.assertNotRegex('G/B', regex)
        self.assertNotRegex('-1', regex)

    def test_mana_regex(self):
        self.assertRegex('{W}', MANA_REGEX)
        self.assertRegex('{U}', MANA_REGEX)
        self.assertRegex('{B}', MANA_REGEX)
        self.assertRegex('{R}', MANA_REGEX)
        self.assertRegex('{G}', MANA_REGEX)
        self.assertRegex('{C}', MANA_REGEX)
        self.assertRegex('{P}{2}{P}', MANA_REGEX)
        self.assertRegex('{W/P}', MANA_REGEX)
        self.assertRegex('{U/P}', MANA_REGEX)
        self.assertRegex('{B/P}', MANA_REGEX)
        self.assertRegex('{R/P}', MANA_REGEX)
        self.assertRegex('{G/P}', MANA_REGEX)
        self.assertRegex('{W/U}', MANA_REGEX)
        self.assertRegex('{W/B}', MANA_REGEX)
        self.assertRegex('{U/B}', MANA_REGEX)
        self.assertRegex('{U/R}', MANA_REGEX)
        self.assertRegex('{B/R}', MANA_REGEX)
        self.assertRegex('{B/G}', MANA_REGEX)
        self.assertRegex('{R/G}', MANA_REGEX)
        self.assertRegex('{0}', MANA_REGEX)
        self.assertRegex('{1}', MANA_REGEX)
        self.assertRegex('{2}', MANA_REGEX)
        self.assertRegex('{3}', MANA_REGEX)
        self.assertRegex('{4}', MANA_REGEX)
        self.assertRegex('{5}', MANA_REGEX)
        self.assertRegex('{16}', MANA_REGEX)
        self.assertRegex('{X}', MANA_REGEX)
        self.assertRegex('{Y}', MANA_REGEX)
        self.assertRegex('{Z}', MANA_REGEX)
        self.assertRegex('{S}', MANA_REGEX)
        self.assertRegex('{W/U/P}', MANA_REGEX)
        self.assertRegex('{W/B/P}', MANA_REGEX)
        self.assertRegex('{U/B/P}', MANA_REGEX)
        self.assertRegex('{U/R/P}', MANA_REGEX)
        self.assertRegex('{B/R/P}', MANA_REGEX)
        self.assertRegex('{B/G/P}', MANA_REGEX)
        self.assertRegex('{R/G/P}{W}', MANA_REGEX)
        self.assertRegex('{R/G/P}{C} and {W}', MANA_REGEX)
        self.assertRegex('{W}{W}{U}{U} each turn.', MANA_REGEX)
        self.assertNotRegex('[R/G/P]', MANA_REGEX)
        self.assertNotRegex('{R} and }U}', MANA_REGEX)

    def test_double_square_bracket_text(self):
        self.assertRegex('[[Black Lotus]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertRegex('[[random]] and [[stuff]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertRegex('[[random]] and [[stuff]] and [[more stuff]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertRegex('[[random]] and [[stuff]] and [[more stuff]] and [[even more stuff]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertRegex('[ [ any single square bracket is fine ] anyway ] []', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertRegex('[[[ triple square brackets are ] fine too ]]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertNotRegex('[[]]', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)
        self.assertNotRegex('[[', DOUBLE_SQUARE_BRACKET_TEXT_REGEX)

    def test_oracle_symbol(self):
        regex = f'^{ORACLE_SYMBOL}$'
        self.assertRegex('T', regex)
        self.assertRegex('Q', regex)
        self.assertRegex('E', regex)
        self.assertRegex('A', regex)
        self.assertRegex('½', regex)
        self.assertRegex('CHAOS', regex)
        self.assertRegex('∞', regex)
        for i in range(100):
            self.assertRegex(str(i), regex)
        for x in 'WUBRG':
            self.assertRegex(x, regex)
            self.assertRegex(f'H{x}', regex)
            self.assertRegex(f'2/{x}', regex)
        self.assertRegex('C', regex)
        self.assertRegex('P', regex)
        self.assertRegex('X', regex)
        self.assertRegex('Y', regex)
        self.assertRegex('Z', regex)
        self.assertRegex('S', regex)
        self.assertRegex('W/U', regex)
        self.assertRegex('W/B', regex)
        self.assertRegex('U/B', regex)
        self.assertRegex('U/R', regex)
        self.assertRegex('B/R/P', regex)
        self.assertRegex('B/G', regex)
        self.assertRegex('R/G', regex)
        self.assertRegex('R/G/P', regex)
        self.assertRegex('W/U/P', regex)
        self.assertNotRegex('W/U/P/', regex)
        self.assertNotRegex('W/U/P/P', regex)
        self.assertNotRegex('U/W', regex)
        self.assertNotRegex('WU', regex)
        self.assertNotRegex('WU/P', regex)
        self.assertNotRegex('J', regex)

    def test_symbols_text(self):
        self.assertRegex('{T}: Add {W}{U}{B}{R}{G}.', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{T}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{Q}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{E}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{A}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{½}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{CHAOS}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{∞}', SYMBOLS_TEXT_REGEX)
        for i in range(100):
            self.assertRegex(f'{{{i}}}', SYMBOLS_TEXT_REGEX)
        for x in 'WUBRG':
            self.assertRegex(f'{{{x}}}', SYMBOLS_TEXT_REGEX)
            self.assertRegex(f'{{H{x}}}', SYMBOLS_TEXT_REGEX)
            self.assertRegex(f'{{2/{x}}}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{C} {P} {X} anything {X}{Y}{Z}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{W/U} {W/B} {U/B} {U/R} {B/R/P} {B/G} {R/G} {R/G/P} {W/U/P}', SYMBOLS_TEXT_REGEX)
        self.assertRegex('{W/U/P} {W/B/P} {U/B/P} {U/R/P} {B/R/P} {B/G/P} {R/G/P} {R/G/P}{W}', SYMBOLS_TEXT_REGEX)
        self.assertNotRegex('{W/U/P/}', SYMBOLS_TEXT_REGEX)
        self.assertNotRegex('{W/U/P{}', SYMBOLS_TEXT_REGEX)

    def test_scryfall_query(self):
        self.assertRegex('c:rg', SCRYFALL_QUERY_REGEX)
        self.assertRegex('color>=uw -c:red', SCRYFALL_QUERY_REGEX)
        self.assertRegex('id<=esper t:instant', SCRYFALL_QUERY_REGEX)
        self.assertRegex('id:c t:land', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:merfolk t:legend', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:goblin -t:creature', SCRYFALL_QUERY_REGEX)
        self.assertRegex('mana:{G}{U}', SCRYFALL_QUERY_REGEX)
        self.assertRegex('m:{2}{W}{W}', SCRYFALL_QUERY_REGEX)
        self.assertRegex('m>{3}{W}{U}', SCRYFALL_QUERY_REGEX)
        self.assertRegex('m:{R/P}', SCRYFALL_QUERY_REGEX)
        self.assertRegex('c:u mv=5', SCRYFALL_QUERY_REGEX)
        self.assertRegex('devotion:{U/B}{U/B}{U/B}', SCRYFALL_QUERY_REGEX)
        self.assertRegex('produces=wu', SCRYFALL_QUERY_REGEX)
        self.assertRegex('pow>=8', SCRYFALL_QUERY_REGEX)
        self.assertRegex('pow>tou c:w t:creature', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:planeswalker loy=3', SCRYFALL_QUERY_REGEX)
        self.assertRegex('is:meld', SCRYFALL_QUERY_REGEX)
        self.assertRegex('is:split', SCRYFALL_QUERY_REGEX)
        self.assertRegex('c>=br is:spell', SCRYFALL_QUERY_REGEX)
        self.assertRegex('is:permanent t:rebel', SCRYFALL_QUERY_REGEX)
        self.assertRegex('is:vanilla', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:fish or t:bird', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:land (c:wu or pow<6)', SCRYFALL_QUERY_REGEX)
        self.assertRegex('t:legendary (t:goblin or t:elf)', SCRYFALL_QUERY_REGEX)
        self.assertRegex('pt>9 (mv<6 or pow>6 or tou>6)', SCRYFALL_QUERY_REGEX)
        self.assertNotRegex('asd', SCRYFALL_QUERY_REGEX)
        self.assertNotRegex('c:rg ', SCRYFALL_QUERY_REGEX)
        self.assertNotRegex('kek:stuff', SCRYFALL_QUERY_REGEX)
        self.assertNotRegex('--t:card', SCRYFALL_QUERY_REGEX)
        self.assertNotRegex('t:card or and t:card', SCRYFALL_QUERY_REGEX)
