from django.core.exceptions import ValidationError
from spellbook.models import Card, OracleTag, OracleTagName, CardOracleTag, oracle_tag_key
from spellbook.transformers.scryfall_query_transformer import scryfall_query_parser
from .testing import SpellbookTestCaseWithSeeding, curated_card


def matching(query: str) -> set[str]:
    '''The cards of this module's own fixture that the query names, so that the seeded ones stay out of it.'''
    return set(
        Card.objects
        .filter(scryfall_query_parser(query), name__startswith='Test ')
        .values_list('name', flat=True)
    )


class ScryfallQueryTests(SpellbookTestCaseWithSeeding):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.bear = curated_card(name='Test Bear', type_line='Creature — Bear', oracle_text='Test Bear is big.', mana_cost='{1}{G}', mana_value=2, power='2', toughness='2', power_value=2, toughness_value=2, color='G', identity='G', layout='normal', keywords=['Trample'], produced_mana=[])
        cls.dork = curated_card(name='Test Dork', type_line='Creature — Elf', oracle_text='{T}: Add {G}.', mana_cost='{G}', mana_value=1, power='1', toughness='1', power_value=1, toughness_value=1, color='G', identity='G', layout='normal', produced_mana=['G'])
        cls.land = curated_card(name='Test Land', type_line='Land', oracle_text='{T}: Add {U}.', mana_cost='', mana_value=0, color='C', identity='U', layout='normal', produced_mana=['U'])
        # the only card here whose power and toughness differ, which is what comparing the two turns on
        cls.ogre = curated_card(name='Test Ogre', type_line='Creature — Ogre', oracle_text='Test Ogre attacks each combat if able.', mana_cost='{2}{R}', mana_value=3, power='4', toughness='1', power_value=4, toughness_value=1, color='R', identity='R', layout='normal', produced_mana=[])
        cls.goyf = curated_card(name='Test Goyf', type_line='Creature — Lhurgoyf', oracle_text='Star power.', mana_cost='{1}{G}', mana_value=2, power='*', toughness='1+*', color='G', identity='G', layout='normal')
        # the only card here whose text runs to a second line, which is what a regular expression anchors to
        cls.rock = curated_card(name='Test Rock', type_line='Artifact', oracle_text='Test Rock enters tapped.\n{T}: Add {C}.', mana_cost='{2}', mana_value=2, color='C', identity='C', layout='normal', produced_mana=['C'])

    def test_a_type_and_a_number_narrow_each_other(self):
        self.assertEqual(matching('t:creature mv<=1'), {'Test Dork'})

    def test_juxtaposition_and_the_and_keyword_mean_the_same(self):
        self.assertEqual(matching('t:creature mv=2'), matching('t:creature and mv=2'))

    def test_or_widens(self):
        self.assertEqual(matching('t:land or t:bear'), {'Test Land', 'Test Bear'})

    def test_de_morgan_holds_over_a_group(self):
        self.assertEqual(matching('-(t:land or t:bear)'), matching('-t:land -t:bear'))

    def test_negation_of_a_conjunction_is_the_disjunction_of_the_negations(self):
        self.assertEqual(matching('-(t:creature mv=2)'), matching('-t:creature or -mv=2'))

    def test_a_group_binds_tighter_than_juxtaposition(self):
        self.assertEqual(matching('(t:land or t:elf) t:creature'), {'Test Dork'})
        self.assertNotEqual(matching('(t:land or t:elf) t:creature'), matching('t:land or t:elf t:creature'))

    def test_three_levels_of_nesting(self):
        self.assertEqual(
            matching('(t:creature (mv=1 or (mv=2 -t:lhurgoyf))) -o:"star power"'),
            {'Test Dork', 'Test Bear'},
        )

    def test_a_characteristic_that_is_not_a_number_matches_nothing_numeric(self):
        self.assertEqual(matching('pow>=0 t:lhurgoyf'), set())
        self.assertEqual(matching('pow!=0 t:lhurgoyf'), set())
        self.assertEqual(matching('t:lhurgoyf'), {'Test Goyf'})

    def test_a_characteristic_compares_to_another_characteristic(self):
        self.assertEqual(matching('pow>tou'), {'Test Ogre'})
        self.assertEqual(matching('pow=tou'), {'Test Bear', 'Test Dork'})
        self.assertEqual(matching('pow<tou'), set())
        self.assertEqual(matching('mv>=pow'), {'Test Bear', 'Test Dork'})

    def test_comparing_two_characteristics_needs_a_number_on_both_sides(self):
        # the Lhurgoyf prints * and 1+*, so neither side of the comparison is a number
        self.assertEqual(matching('pow=tou t:lhurgoyf'), set())
        self.assertEqual(matching('pow!=tou t:lhurgoyf'), set())

    def test_total_power_and_toughness_adds_the_two(self):
        self.assertEqual(matching('pt=4'), {'Test Bear'})
        self.assertEqual(matching('powtou<=2'), {'Test Dork'})
        self.assertEqual(matching('pt>mv'), {'Test Bear', 'Test Dork', 'Test Ogre'})

    def test_an_exact_name_matches_the_whole_name(self):
        self.assertEqual(matching('!"Test Bear"'), {'Test Bear'})
        self.assertEqual(matching('!"Test"'), set())

    def test_mana_cost_containment_equality_and_subset(self):
        self.assertEqual(matching('mana:{G}'), {'Test Bear', 'Test Dork', 'Test Goyf'})
        self.assertEqual(matching('mana={G}'), {'Test Dork'})
        self.assertEqual(matching('mana={1}{G}'), {'Test Bear', 'Test Goyf'})
        # a card printing no cost at all is below every cost, which is how -m<{0} keeps lands out
        self.assertEqual(matching('m<{0}'), {'Test Land'})
        self.assertEqual(matching('t:land -m<{0}'), set())

    def test_produces_reads_the_mana_the_card_makes(self):
        self.assertEqual(matching('produces:G'), {'Test Dork'})
        self.assertEqual(matching('produces:U'), {'Test Land'})

    def test_colors_compare_as_sets(self):
        self.assertEqual(matching('c:G t:creature'), {'Test Bear', 'Test Dork', 'Test Goyf'})
        self.assertEqual(matching('c=0 t:land'), {'Test Land'})

    def test_a_regex_reads_one_line_of_the_oracle_text(self):
        # the ability is on the second line, so anchoring to the start of the whole text would miss it
        self.assertEqual(matching('o:/^{T}: Add/'), {'Test Rock', 'Test Dork', 'Test Land'})
        self.assertEqual(matching('o:/^Test Rock enters/'), {'Test Rock'})

    def test_a_regex_does_not_run_a_negated_class_past_the_end_of_a_line(self):
        # PostgreSQL stops one there itself, and Python, which is what SQLite runs, has to be told to
        self.assertEqual(matching('o:/^Test Rock[^Z]+tapped/'), {'Test Rock'})
        self.assertEqual(matching('o:/^Test Rock[^Z]+Add/'), set())

    def test_a_tilde_in_a_regex_stands_for_the_name_of_the_card(self):
        self.assertEqual(matching('o:/^~ enters tapped/'), {'Test Rock'})

    def test_a_regex_that_could_take_exponential_time_is_refused(self):
        with self.assertRaises(ValidationError):
            scryfall_query_parser('o:/(a+)+b/')

    def test_an_oracle_tag_resolves_through_every_name_it_answers_to(self):
        tag = OracleTag.objects.create(id='00000000-0000-0000-0000-0000000000aa', slug='creatureland', label='creatureland')
        # the shape Scryfall publishes: a slug and an alias carrying a space, each under the key it reduces to
        for name in ('creatureland', 'man land'):
            OracleTagName.objects.create(tag=tag, name=name, normalized_name=oracle_tag_key(name))
        CardOracleTag.objects.create(card=self.land, tag=tag)
        self.assertEqual(matching('otag:creatureland'), {'Test Land'})
        self.assertEqual(matching('otag:manland'), {'Test Land'})
        self.assertEqual(matching('otag:man-land'), {'Test Land'})
        self.assertEqual(matching('otag:Man-Land'), {'Test Land'})

    def test_an_unknown_oracle_tag_names_no_card(self):
        self.assertEqual(matching('otag:no-such-tag'), set())

    def test_reading_a_query_asks_the_database_nothing(self):
        with self.assertNumQueries(0):
            scryfall_query_parser('otag:creatureland otag:man-land t:creature')

    def test_an_unreadable_query_is_rejected(self):
        with self.assertRaises(ValidationError):
            scryfall_query_parser('t:creature (')
