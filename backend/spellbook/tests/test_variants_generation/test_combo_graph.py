from multiset import FrozenMultiset
from spellbook.models import Combo
from spellbook.variants.variant_data import Data
from spellbook.variants.combo_graph import Graph, VariantIngredients, VariantSet, VariantRecipe
from spellbook.tests.abstract_test import AbstractTestCaseWithSeeding, AbstractTestCase


class ComboGraphTest(AbstractTestCaseWithSeeding):
    def test_empty_graph(self):
        Combo.objects.exclude(id=self.b2_id).delete()
        combo_graph = Graph(Data())
        self.assertCountEqual(combo_graph.results(combo_graph.variants(self.b2_id)), [])

    def test_variants(self):
        combo_graph = Graph(Data())
        variants = combo_graph.variants(self.b2_id)
        self.assertEqual(len(variants), 3)
        self.assertIsInstance(variants, VariantSet)

    def test_results(self):
        combo_graph = Graph(Data())
        variants = combo_graph.variants(self.b2_id)
        results = combo_graph.results(variants)
        self.assertEqual(len(list(results)), 3)
        for result in results:
            self.assertIsInstance(result, VariantRecipe)

    def test_graph(self):
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(self.b2_id)))
        self.assertEqual(variants, list(combo_graph.results(combo_graph.variants(self.b2_id))))
        self.assertEqual(len(variants), 3)

    def test_variant_limit(self):
        combo_graph = Graph(Data(), log=lambda _: None, variant_limit=0)
        self.assertRaises(Graph.GraphError, lambda: combo_graph.variants(self.b2_id))
        combo_graph = Graph(Data(), log=lambda _: None, variant_limit=1)
        self.assertRaises(Graph.GraphError, lambda: combo_graph.variants(self.b2_id))
        combo_graph = Graph(Data(), log=lambda _: None, variant_limit=20)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 3)

    def test_default_log(self):
        def test():
            combo_graph = Graph(Data(), variant_limit=0)
            list(combo_graph.results(combo_graph.variants(self.b2_id)))
        self.assertRaises(Exception, test)

    def test_card_limit(self):
        self.maxDiff = None
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=0)
        self.assertCountEqual(combo_graph.results(combo_graph.variants(self.b2_id)), [])
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=1)
        self.assertCountEqual(combo_graph.results(combo_graph.variants(self.b2_id)), [])
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=2)
        self.assertCountEqual(combo_graph.results(combo_graph.variants(self.b2_id)), [])
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=3)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 1)
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=4)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 2)
        combo_graph = Graph(Data(), log=lambda _: None, card_limit=5)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 3)

    def test_allow_multiple_copies(self):
        self.maxDiff = None
        c = Combo.objects.get(id=self.b4_id)
        card_needed = c.cardincombo_set.first()
        assert card_needed is not None
        card_needed.quantity = 2
        card_needed.save()
        combo_graph = Graph(Data(), log=lambda _: None, allow_multiple_copies=False)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 2)
        combo_graph = Graph(Data(), log=lambda _: None, allow_multiple_copies=True)
        self.assertEqual(len(list(combo_graph.results(combo_graph.variants(self.b2_id)))), 3)

    def test_replacements(self):
        data = Data()
        combo_graph = Graph(data=data)
        variants = list(combo_graph.results(combo_graph.variants(self.b2_id)))
        for variant in variants:
            card_ids = {c for c in variant.cards}
            template_ids = {t for t in variant.templates}
            replacements = variant.replacements
            feature_needed_by_combos = {f.id for f in data.id_to_combo[self.b2_id].features_needed()}  # type: set[int]
            self.assertTrue(set(replacements.keys()).issuperset(feature_needed_by_combos))
            for replacement_values in replacements.values():
                self.assertGreaterEqual(len(replacement_values), 1)
                for replacement_value in replacement_values:
                    cards = replacement_value.cards
                    templates = replacement_value.templates
                    replacement_card_ids = {c for c in cards}
                    replacement_template_ids = {t for t in templates}
                    self.assertTrue(card_ids.issuperset(replacement_card_ids))
                    self.assertTrue(template_ids.issuperset(replacement_template_ids))


class ComboGraphTestGeneration(AbstractTestCase):
    def assertReplacementsEqual(self, replacements: dict[int, list[VariantIngredients]], expected: dict[int, list[VariantIngredients]]):
        self.assertEqual(len(replacements), len(expected))
        for replacement in replacements:
            self.assertIn(replacement, expected)
            self.assertSetEqual(set(replacements[replacement]), set(expected[replacement]))

    def test_one_card_combo(self):
        self.save_combo_model({
            ('A',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 1})
        self.assertReplacementsEqual(variants[0].replacements, {1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())]})

    def test_one_card_combo_with_replacement(self):
        self.save_combo_model({
            'A': ('x',),
            ('x',): ('y',),
        })
        combo_graph = Graph(Data())
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })

    def test_two_one_card_combo(self):
        self.save_combo_model({
            ('A',): ('x',),
            ('B',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 1})
        self.assertReplacementsEqual(variants[0].replacements, {1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())]})
        variants = combo_graph.results(combo_graph.variants(2))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {2: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {2})
        self.assertMultisetEqual(variants[0].features, {1: 1})
        self.assertReplacementsEqual(variants[0].replacements, {1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())]})

    def test_card_plus_template(self):
        self.save_combo_model({
            ('A', 'T1'): ('x', 'y'),
        })
        combo_graph = Graph(Data())
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {1: 1})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset({1: 1}))],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset({1: 1}))],
        })

    def test_feature_replacement(self):
        self.save_combo_model({
            ('A',): ('x',),
            ('B',): ('x',),
            ('x',): ('y',),
        })
        combo_graph = Graph(Data())
        variants = combo_graph.results(combo_graph.variants(3))
        self.assertEqual(len(list(variants)), 2)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1, 3})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {2: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertSetEqual(variants[1].combos, {2, 3})
        self.assertMultisetEqual(variants[1].features, {1: 1, 2: 1})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
        })

    def test_replacement_with_multiple_copies(self):
        self.save_combo_model({
            'A': ('x',),
            ('2 * x',): ('y',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 0)

    def test_replacement_with_functional_reprints(self):
        self.save_combo_model({
            'A': ('x',),
            '3 * B': ('x',),
            ('2 * x',): ('y',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 3)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertSetEqual(variants[0].combos, {1})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 2: 3})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertSetEqual(variants[1].combos, {1})
        self.assertMultisetEqual(variants[1].features, {1: 2, 2: 1})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 3}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[2].cards, {2: 6})
        self.assertMultisetEqual(variants[2].templates, {})
        self.assertSetEqual(variants[2].combos, {1})
        self.assertMultisetEqual(variants[2].features, {1: 2, 2: 1})
        self.assertReplacementsEqual(variants[2].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 6}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = combo_graph.results(combo_graph.variants(1))
        self.assertEqual(len(list(variants)), 0)

    def test_feature_replacement_chain(self):
        self.save_combo_model({
            ('A',): ('x',),
            ('B',): ('x',),
            ('x',): ('y',),
            ('y',): ('z',),
        })
        combo_graph = Graph(Data())
        variants_a = combo_graph.results(combo_graph.variants(4))
        variants_b = combo_graph.results(combo_graph.variants(4))
        variants_a.sort(key=lambda v: sorted(v.cards))
        variants_b.sort(key=lambda v: sorted(v.cards))
        self.assertEqual(variants_a, variants_b)
        self.assertMultisetEqual(variants_a[0].features, {1: 1, 2: 1, 3: 1})
        self.assertSetEqual(variants_a[0].combos, {1, 3, 4})

    def test_feature_replacement_multiples_cards(self):
        self.save_combo_model({
            ('2 * A',): ('x',),
            ('B',): ('x',),
            ('x',): ('y',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 2)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {2: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[1].combos, {2, 3})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {2: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[0].combos, {2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
        })

    def test_feature_replacement_multiplication(self):
        self.save_combo_model({
            ('2 * A',): ('x',),
            ('3 * B',): ('x',),
            ('2 * x',): ('y',),
            ('x',): ('z',),
            ('z',): ('k',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 3)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 4})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1, 3: 2, 4: 2})
        self.assertSetEqual(variants[0].combos, {1, 3, 4, 5})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 4}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 2, 2: 3})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 2, 2: 1, 3: 2, 4: 2})
        self.assertSetEqual(variants[1].combos, {1, 2, 3, 4, 5})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2, 2: 3}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[2].cards, {2: 6})
        self.assertMultisetEqual(variants[2].templates, {})
        self.assertMultisetEqual(variants[2].features, {1: 2, 2: 1, 3: 2, 4: 2})
        self.assertSetEqual(variants[2].combos, {2, 3, 4, 5})
        self.assertReplacementsEqual(variants[2].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 6}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({2: 3}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 0)

    def test_removal_of_redundant_variants(self):
        self.save_combo_model({
            ('A', 'B'): ('x',),
            ('C', 'D'): ('y',),
            ('x', 'y'): ('z',),
            ('B', 'C'): ('x', 'y'),
        })
        for boolean in (False, True):
            combo_graph = Graph(Data(), allow_multiple_copies=boolean)
            variants = list(combo_graph.results(combo_graph.variants(3)))
            self.assertEqual(len(variants), 1)
            self.assertMultisetEqual(variants[0].cards, {2: 1, 3: 1})
            self.assertMultisetEqual(variants[0].templates, {})
            self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1, 3: 1})
            self.assertSetEqual(variants[0].combos, {3, 4})
            self.assertReplacementsEqual(variants[0].replacements, {
                1: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
                2: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
                3: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            })

    def test_removal_of_redundant_variants_with_multiples(self):
        self.save_combo_model({
            ('3 * A',): ('x',),
            ('3 * B',): ('y',),
            ('x', 'y'): ('z',),
            ('2 * A', '2 * B'): ('x', 'y'),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 2, 2: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1, 3: 1})
        self.assertSetEqual(variants[0].combos, {3, 4})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 2, 2: 2}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2, 2: 2}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({1: 2, 2: 2}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 0)

    def test_result_ring(self):
        self.save_combo_model({
            ('A',): ('x',),
            ('x',): ('z',),
            ('B',): ('w',),
            ('w',): ('z',),
            ('A', 'B'): ('a',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(5)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1, 2: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 2, 3: 1, 4: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3, 4, 5})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset())],
        })

    def test_cross_merge(self):
        self.save_combo_model({
            ('A', 'B'): ('x',),
            ('B', 'C'): ('x',),
            ('2 * x',): ('y',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 3)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 2, 2: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2, 2: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 2: 2, 3: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[1].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 2, 3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[2].cards, {2: 2, 3: 2})
        self.assertMultisetEqual(variants[2].templates, {})
        self.assertMultisetEqual(variants[2].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[2].combos, {2, 3})
        self.assertReplacementsEqual(variants[2].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 2, 3: 2}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1, 2: 2, 3: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 2, 3: 1}), FrozenMultiset())],
        })

    def test_opportunistic_choice(self):
        self.save_combo_model({
            ('A', 'B'): ('x',),
            ('A',): ('x',),
            ('C',): ('x',),
            ('x',): ('y',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(4)))
        self.assertEqual(len(variants), 2)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[0].combos, {2, 4})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {3: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[1].combos, {3, 4})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
        })

    def test_combinations_of_requisites(self):
        self.save_combo_model({
            ('A',): ('x',),
            ('B',): ('x',),
            ('C',): ('x',),
            ('2 * x',): ('y',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(4)))
        self.assertEqual(len(variants), 6)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 2})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 4})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 2: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[1].combos, {1, 2, 4})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[2].cards, {1: 1, 3: 1})
        self.assertMultisetEqual(variants[2].templates, {})
        self.assertMultisetEqual(variants[2].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[2].combos, {1, 3, 4})
        self.assertReplacementsEqual(variants[2].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[3].cards, {2: 2})
        self.assertMultisetEqual(variants[3].templates, {})
        self.assertMultisetEqual(variants[3].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[3].combos, {2, 4})
        self.assertReplacementsEqual(variants[3].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 2}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[4].cards, {2: 1, 3: 1})
        self.assertMultisetEqual(variants[4].templates, {})
        self.assertMultisetEqual(variants[4].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[4].combos, {2, 3, 4})
        self.assertReplacementsEqual(variants[4].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[5].cards, {3: 2})
        self.assertMultisetEqual(variants[5].templates, {})
        self.assertMultisetEqual(variants[5].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[5].combos, {3, 4})
        self.assertReplacementsEqual(variants[5].replacements, {
            1: [VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({3: 2}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(4)))
        self.assertEqual(len(variants), 3)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 1, 2: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 4})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 3: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[1].combos, {1, 3, 4})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[2].cards, {2: 1, 3: 1})
        self.assertMultisetEqual(variants[2].templates, {})
        self.assertMultisetEqual(variants[2].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[2].combos, {2, 3, 4})
        self.assertReplacementsEqual(variants[2].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1}), FrozenMultiset()), VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
        })

    def test_chained_multiplication(self):
        self.save_combo_model({
            ('5 * A',): ('x',),
            ('2 * x',): ('y',),
            ('3 * y',): ('z',),
        })
        combo_graph = Graph(Data(), allow_multiple_copies=True)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 30})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 6, 2: 3, 3: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 5}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 10}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({1: 30}), FrozenMultiset())],
        })
        combo_graph = Graph(Data(), allow_multiple_copies=False)
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 0)

    def test_unsolvable_trivial_loop(self):
        self.save_combo_model({
            ('x',): ('y',),
            ('y',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(2)))
        self.assertEqual(len(variants), 0)

    def test_solvable_trivial_loop(self):
        self.save_combo_model({
            ('x',): ('y',),
            ('y',): ('x',),
            ('A',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(2)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })

    def test_unsolvable_loop(self):
        self.save_combo_model({
            ('x',): ('y',),
            ('y',): ('z',),
            ('z',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(2)))
        self.assertEqual(len(variants), 0)

    def test_solvable_loop(self):
        self.save_combo_model({
            ('x',): ('y',),
            ('y',): ('z',),
            ('z',): ('x',),
            ('A',): ('x',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(3)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 2, 2: 1, 3: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3, 4})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })

    def test_additional_results(self):
        self.save_combo_model({
            ('A', 'f'): ('z',),
            ('B', 'g'): ('f',),
            ('C',): ('g',),
            ('D',): ('g',),
            ('A', 'D',): ('y',),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(1)))
        self.assertEqual(len(variants), 2)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 1, 2: 1, 3: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1, 3: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 1, 3: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 2: 1, 4: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 1, 2: 1, 3: 1, 4: 1})
        self.assertSetEqual(variants[1].combos, {1, 2, 4, 5})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1, 4: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 1, 4: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({4: 1}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({1: 1, 4: 1}), FrozenMultiset())],
        })

    def test_variant_removal(self):
        self.save_combo_model({
            ('A', 'f'): ('z',),
            ('B', 'g'): ('f',),
            ('C',): ('g',),
            ('D',): ('g', 'f', 'y'),
        })
        combo_graph = Graph(Data())
        variants = list(combo_graph.results(combo_graph.variants(1)))
        self.assertEqual(len(variants), 2)
        variants.sort(key=lambda v: sorted(v.cards))
        self.assertMultisetEqual(variants[0].cards, {1: 1, 2: 1, 3: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1, 3: 1})
        self.assertSetEqual(variants[0].combos, {1, 2, 3})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({2: 1, 3: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 2: 1, 3: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({3: 1}), FrozenMultiset())],
        })
        self.assertMultisetEqual(variants[1].cards, {1: 1, 4: 1})
        self.assertMultisetEqual(variants[1].templates, {})
        self.assertMultisetEqual(variants[1].features, {1: 1, 2: 1, 3: 1, 4: 1})
        self.assertSetEqual(variants[1].combos, {1, 4})
        self.assertReplacementsEqual(variants[1].replacements, {
            1: [VariantIngredients(FrozenMultiset({4: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1, 4: 1}), FrozenMultiset())],
            3: [VariantIngredients(FrozenMultiset({4: 1}), FrozenMultiset())],
            4: [VariantIngredients(FrozenMultiset({4: 1}), FrozenMultiset())],
        })

    def test_additional_results_avoiding_too_many_variants(self):
        threshold = 100
        self.save_combo_model({
            ('A',): ('x',),
            ('x',): ('y',),
            **{(f'B{i}',): ('x',) for i in range(threshold + 1)},
        })
        combo_graph = Graph(Data(), variant_limit=threshold)
        self.assertRaises(Exception, lambda: combo_graph.variants(2))
        variants = list(combo_graph.results(combo_graph.variants(1)))
        self.assertEqual(len(variants), 1)
        self.assertMultisetEqual(variants[0].cards, {1: 1})
        self.assertMultisetEqual(variants[0].templates, {})
        self.assertMultisetEqual(variants[0].features, {1: 1, 2: 1})
        self.assertSetEqual(variants[0].combos, {1, 2})
        self.assertReplacementsEqual(variants[0].replacements, {
            1: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
            2: [VariantIngredients(FrozenMultiset({1: 1}), FrozenMultiset())],
        })
