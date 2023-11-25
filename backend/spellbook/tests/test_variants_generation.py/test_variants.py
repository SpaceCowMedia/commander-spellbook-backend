from django.test import TestCase
from spellbook.variants.minimal_set_of_sets import MinimalSetOfSets
from spellbook.variants.variant_set import VariantSet
from spellbook.models import Variant, Combo, Feature, Card, Template, id_from_cards_and_templates_ids, merge_identities
from spellbook.variants.list_utils import includes_any, list_of_tuples_of_lists_to_set
from spellbook.variants.variant_data import Data, debug_queries
from spellbook.variants.combo_graph import Graph
from spellbook.utils import launch_job_command
from spellbook.tests.abstract_test import AbstractModelTests


class ListUtilsTests(TestCase):

    def test_merge_identities(self):
        self.assertEqual(merge_identities(['', '']), 'C')
        for c in 'CWUBRG':
            self.assertEqual(merge_identities([c, '']), c)
            self.assertEqual(merge_identities(['', c]), c)
            self.assertEqual(merge_identities([c, c]), c)
        self.assertEqual(merge_identities(['W', 'U']), 'WU')
        self.assertEqual(merge_identities(['W', 'U', 'B']), 'WUB')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R']), 'WUBR')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R', 'G']), 'WUBRG')
        self.assertEqual(merge_identities(sorted(['W', 'U', 'B', 'R', 'G'])), 'WUBRG')
        self.assertEqual(merge_identities(['W', 'U', 'B', 'R', 'G', 'W']), 'WUBRG')
        self.assertEqual(merge_identities(['WU', 'BR', 'G', 'WG']), 'WUBRG')
        self.assertEqual(merge_identities(['S']), 'C')
        self.assertEqual(merge_identities(['S', 'R']), 'R')
        self.assertEqual(merge_identities(['r', 'g']), 'RG')
        self.assertEqual(merge_identities(['g', 'r']), 'RG')

    def test_includes_any(self):
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3}, {1, 2, 3, 4}]))
        self.assertTrue(includes_any({1, 2, 3}, [{1, 2, 3, 4}, {2}]))
        self.assertTrue(includes_any(set(), [set()]))
        self.assertTrue(includes_any({1}, [{2}, {1}]))


class MinimalSetOfSetsTests(TestCase):

    def setUp(self) -> None:
        self.aset = MinimalSetOfSets({
            frozenset({1, 2, 3}),
            frozenset({1, 2, 3, 4}),
            frozenset({3, 4, 5}),
            frozenset({3, 4, 5, 6}),
            frozenset(range(10)),
        })
        return super().setUp()

    def test_init(self):
        self.assertEqual(set(MinimalSetOfSets()), set())
        self.assertEqual(set(MinimalSetOfSets({frozenset({1})})), {frozenset({1})})
        self.assertEqual(set(MinimalSetOfSets({frozenset({1}), frozenset({2})})), {frozenset({1}), frozenset({2})})
        self.assertEqual(set(MinimalSetOfSets({frozenset({1, 2, 3})})), {frozenset({1, 2, 3})})
        self.assertEqual(set(self.aset), {
            frozenset({1, 2, 3}),
            frozenset({3, 4, 5}),
        })

    def test_contains_subset(self):
        self.assertFalse(MinimalSetOfSets().contains_subset_of({1}))
        self.assertTrue(MinimalSetOfSets({frozenset({1})}).contains_subset_of({1}))
        self.assertFalse(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1, 2}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({1, 2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 4}))
        self.assertFalse(MinimalSetOfSets({frozenset({1, 2, 6}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 5}))
        self.assertTrue(MinimalSetOfSets({frozenset({2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3}))
        self.assertTrue(MinimalSetOfSets({frozenset({2}), frozenset({1, 2, 4})}).contains_subset_of({1, 2, 3, 4}))
        self.assertTrue(self.aset.contains_subset_of(frozenset(range(100))))
        self.assertFalse(self.aset.contains_subset_of(frozenset(range(7, 10))))

    def test_add(self):
        self.aset.add(frozenset({1, 2, 3, 4, 5}))
        self.assertEqual(set(self.aset), {frozenset({1, 2, 3}), frozenset({3, 4, 5})})
        self.aset.add(frozenset(range(50, 100)))
        self.assertEqual(set(self.aset), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.aset.add(frozenset(range(50, 100)))
        self.assertEqual(set(self.aset), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.aset.add(frozenset({1, 2, 3, 4}))
        self.assertEqual(set(self.aset), {frozenset({1, 2, 3}), frozenset({3, 4, 5}), frozenset(range(50, 100))})
        self.aset.add(frozenset({3}))
        self.aset.add(frozenset({69}))
        self.assertEqual(set(self.aset), {frozenset({3}), frozenset({69})})
        self.aset.add(frozenset({}))
        self.assertEqual(set(self.aset), {frozenset({})})

    def test_union(self):
        self.assertEqual(self.aset, MinimalSetOfSets.union(MinimalSetOfSets(), self.aset))
        self.assertEqual(self.aset, MinimalSetOfSets.union(self.aset, MinimalSetOfSets()))
        self.assertEqual(self.aset, MinimalSetOfSets.union(self.aset, self.aset))
        other = MinimalSetOfSets({
            frozenset({1, 2, 3, 4, 5}),
            frozenset(range(50, 100)),
            frozenset({3}),
        })
        self.assertEqual(set(MinimalSetOfSets.union(self.aset, other)), {
            frozenset({3}),
            frozenset(range(50, 100)),
        })

    def test_len(self):
        self.aset.add(frozenset({1, 2, 3, 4, 5}))
        self.assertEqual(len(self.aset), 2)
        self.aset.add(frozenset(range(50, 100)))
        self.assertEqual(len(self.aset), 3)
        self.aset.add(frozenset(range(50, 100)))
        self.assertEqual(len(self.aset), 3)
        self.aset.add(frozenset({1, 2, 3, 4}))
        self.assertEqual(len(self.aset), 3)
        self.aset.add(frozenset({3}))
        self.aset.add(frozenset({69}))
        self.assertEqual(len(self.aset), 2)
        self.aset.add(frozenset({}))
        self.assertEqual(len(self.aset), 1)

    def test_iter(self):
        self.assertEqual(set(self.aset), {frozenset({1, 2, 3}), frozenset({3, 4, 5})})
        self.assertListEqual(list(self.aset), [frozenset({1, 2, 3}), frozenset({3, 4, 5})])
        self.assertEqual(tuple(self.aset), (frozenset({1, 2, 3}), frozenset({3, 4, 5})))

    def test_contains(self):
        self.assertIn(frozenset({1, 2, 3}), self.aset)
        self.assertIn(frozenset({3, 4, 5}), self.aset)
        self.assertNotIn(frozenset({1, 2, 3, 4}), self.aset)
        self.assertNotIn(frozenset({1, 2, 3, 4, 5}), self.aset)
        self.assertNotIn(frozenset({1}), self.aset)

    def test_copy(self):
        self.assertEqual(self.aset, self.aset.copy())
        c = self.aset.copy()
        c.add(frozenset({}))
        self.assertNotEqual(self.aset, c)
        self.assertNotEqual(len(self.aset), len(c))


class VariantDataTests(AbstractModelTests):
    def test_combos(self):
        data = Data()
        self.assertEqual(len(data.combos), Combo.objects.filter(kind__in=(Combo.Kind.GENERATOR, Combo.Kind.GENERATOR_WITH_MANY_CARDS, Combo.Kind.UTILITY)).count())
        self.assertDictEqual({k: data.combo_to_cards[k] for k in Combo.objects.values_list('id', flat=True)}, {combo.id: list(combo.cardincombo_set.all()) for combo in Combo.objects.all()})
        self.assertDictEqual({k: data.combo_to_templates[k] for k in Combo.objects.values_list('id', flat=True)}, {combo.id: list(combo.templateincombo_set.all()) for combo in Combo.objects.all()})
        self.assertEqual(set(c.id for c in data.generator_combos), set(Combo.objects.filter(kind__in=(Combo.Kind.GENERATOR, Combo.Kind.GENERATOR_WITH_MANY_CARDS)).values_list('id', flat=True)))

    def test_features(self):
        data = Data()
        self.assertEqual(set(data.features.values_list('id', flat=True)), set(Feature.objects.values_list('id', flat=True)))

    def test_cards(self):
        data = Data()
        self.assertEqual(set(data.cards.values_list('id', flat=True)), set(Card.objects.values_list('id', flat=True)))

    def test_variants(self):
        data = Data()
        self.assertEqual(set(data.variants.values_list('id', flat=True)), set(Variant.objects.values_list('id', flat=True)))

    def test_templates(self):
        data = Data()
        self.assertEqual(set(data.templates.values_list('id', flat=True)), set(Template.objects.values_list('id', flat=True)))

    def test_utility_features_ids(self):
        data = Data()
        self.assertSetEqual(data.utility_features_ids, set(Feature.objects.filter(utility=True).values_list('id', flat=True)))

    def test_not_working_variants(self):
        launch_job_command('generate_variants', None)
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        v1.status = Variant.Status.NOT_WORKING
        v1.save()
        data = Data()
        self.assertEqual(data.not_working_variants, [frozenset({self.c8_id, self.c1_id})])
        launch_job_command('generate_variants', None)
        data = Data()
        self.assertEqual(data.not_working_variants, [frozenset({self.c8_id, self.c1_id})] * 2)

    def test_id_to_x(self):
        data = Data()
        self.assertEqual(data.id_to_variant, {v.id: v for v in Variant.objects.all()})
        self.assertEqual(data.id_to_combo, {c.id: c for c in Combo.objects.exclude(kind=Combo.Kind.DRAFT).all()})
        self.assertEqual(data.id_to_card, {c.id: c for c in Card.objects.all()})
        self.assertEqual(data.id_to_template, {t.id: t for t in Template.objects.all()})

    def test_card_in_variant(self):
        data = Data()
        for card_id, variant_id in data.card_in_variant:
            self.assertIn(card_id, set(data.id_to_variant[variant_id].uses.all().values_list('id', flat=True)))

    def test_template_in_variant(self):
        data = Data()
        for template_id, variant_id in data.template_in_variant:
            self.assertIn(template_id, set(data.id_to_variant[variant_id].uses.all().values_list('id', flat=True)))

    def test_combo_to_removed_features(self):
        data = Data()
        for combo_id, removed_feature_ids in data.combo_to_removed_features.items():
            self.assertEqual(removed_feature_ids, set(data.id_to_combo[combo_id].removes.all().values_list('id', flat=True)))

    def test_debug_queries(self):
        with self.settings(DEBUG=True):
            q = debug_queries()
            Variant.objects.all().count()
            self.assertEqual(debug_queries() - q, 1)


class VariantSetTests(TestCase):
    def test_ingredients_to_key(self):
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1, 2, 3, 4], [])), ([1, 2, 3, 4], []))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1, 2, 3, 4], [1, 2, 3])), ([1, 2, 3, 4], [1, 2, 3]))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([], [1, 2, 3])), ([], [1, 2, 3]))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([], [])), ([], []))
        self.assertEqual(VariantSet.key_to_ingredients(VariantSet.ingredients_to_key([1], [1])), ([1], [1]))

    def test_key_to_ingredients(self):
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset())), frozenset())
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1'}))), frozenset({'C1', 'C2', 'T1'}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1', 'T2'}))), frozenset({'C1', 'C2', 'T1', 'T2'}))
        self.assertEqual(VariantSet.ingredients_to_key(*VariantSet.key_to_ingredients(frozenset({'C1', 'C2', 'T1', 'T3'}))), frozenset({'C1', 'C2', 'T1', 'T3'}))

    def test_variant_set_add(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4], [1, 2, 3, 4])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4, 5], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3))})
        variant_set.add([1, 2, 3, 4, 5, 6], [1, 2])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3)), ((1, 2, 3, 4, 5, 6), (1, 2))})
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4), (1, 2, 3)), ((1, 2, 3, 4, 5), (1, 2))})
        variant_set.add([2, 3, 4], [1, 2, 3])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((1, 2, 3, 4, 5), (1, 2)), ((2, 3, 4), (1, 2, 3))})
        variant_set.add([2, 4], [])
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set.variants()), {((2, 4), ())})

    def test_is_satisfied_by(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4], [1, 2, 3]))
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4, 5], [1, 2]))
        self.assertFalse(variant_set.is_satisfied_by([1, 2, 3, 4], [1, 2]))
        self.assertTrue(variant_set.is_satisfied_by([1, 2, 3, 4, 5], [1, 2, 3]))
        self.assertTrue(variant_set.is_satisfied_by([0, 1, 2, 3, 4, 5], [1, 2, 3, 4]))
        self.assertFalse(variant_set.is_satisfied_by([], []))

    def test_len(self):
        variant_set = VariantSet()
        self.assertEqual(len(variant_set), 0)
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(len(variant_set), 1)
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        self.assertEqual(len(variant_set), 2)
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        self.assertEqual(len(variant_set), 2)
        variant_set.add([1, 2, 3, 4], [1, 2])
        self.assertEqual(len(variant_set), 1)

    def test_variant_set_or(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = VariantSet()
        variant_set2.add([1, 2, 3], [1, 2, 3, 4])
        variant_set2.add([1, 2, 3, 4, 5], [1])

        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3]), ([1, 2, 3, 4, 5], [1]), ([1, 2, 3], [1, 2, 3, 4])]))
        variant_set4 = variant_set2 | variant_set
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set(variant_set4.variants()))

        variant_set2.add([2, 3], [2])
        variant_set3 = variant_set | variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([2, 3], [2]), ([1, 2, 3, 4, 5], [1])]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.or_sets([]))
            variant_set5 = VariantSet.or_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(list_of_tuples_of_lists_to_set((variant_set | variant_set2).variants()), list_of_tuples_of_lists_to_set((variant_set2 + variant_set).variants()))
            self.assertEqual(list_of_tuples_of_lists_to_set(VariantSet.or_sets([variant_set, variant_set2, variant_set3]).variants()), list_of_tuples_of_lists_to_set((variant_set2 + variant_set + variant_set3).variants()))

    def test_variant_set_and(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = VariantSet()
        variant_set2.add([1, 2, 3], [1, 2, 3, 4])
        variant_set2.add([1, 2, 3, 4, 5], [1])

        variant_set3 = variant_set & variant_set2
        self.assertEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3, 4]), ([1, 2, 3, 4, 5], [1, 2])]))
        variant_set4 = variant_set2 & variant_set
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set(variant_set4.variants()))

        variant_set2.add([2, 3], [2])
        variant_set3 = variant_set & variant_set2
        self.assertSetEqual(list_of_tuples_of_lists_to_set(variant_set3.variants()), list_of_tuples_of_lists_to_set([([1, 2, 3, 4], [1, 2, 3]), ([1, 2, 3, 4, 5], [1, 2])]))

        with self.subTest('edge cases test'):
            self.assertIsNotNone(VariantSet.and_sets([]))
            variant_set5 = VariantSet.and_sets([variant_set])
            self.assertIsNotNone(variant_set5)
            self.assertFalse(variant_set5 is variant_set)

        with self.subTest('test commutativity and operator overloading'):
            self.assertEqual(list_of_tuples_of_lists_to_set((variant_set & variant_set2).variants()), list_of_tuples_of_lists_to_set((variant_set2 * variant_set).variants()))
            self.assertEqual(list_of_tuples_of_lists_to_set(VariantSet.and_sets([variant_set, variant_set2, variant_set3]).variants()), list_of_tuples_of_lists_to_set((variant_set2 * variant_set * variant_set3).variants()))

    def test_copy(self):
        variant_set = VariantSet()
        variant_set.add([1, 2, 3, 4], [1, 2, 3])
        variant_set.add([1, 2, 3, 4, 5], [1, 2])
        variant_set2 = variant_set.copy()
        self.assertIsNotNone(variant_set2)
        self.assertFalse(variant_set2 is variant_set)
        self.assertEqual(variant_set2.variants(), variant_set.variants())
        variant_set2.add([1, 2], [1, 2])
        self.assertNotEqual(variant_set2.variants(), variant_set.variants())


class ComboGraphTest(AbstractModelTests):
    def test_empty_graph(self):
        Combo.objects.exclude(id=self.b2_id).delete()
        combo_graph = Graph(Data())
        self.assertCountEqual(combo_graph.variants(self.b2_id), [])

    def test_graph(self):
        combo_graph = Graph(Data())
        variants = list(combo_graph.variants(self.b2_id))
        self.assertEqual(variants, list(combo_graph.variants(self.b2_id)))
        self.assertEqual(len(variants), 3)

    def test_variant_limit(self):
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertRaises(Graph.GraphError, lambda: combo_graph.variants(self.b2_id, variant_limit=0))
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertRaises(Graph.GraphError, lambda: combo_graph.variants(self.b2_id, variant_limit=1))
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertEqual(len(list(combo_graph.variants(self.b2_id, variant_limit=20))), 3)

    def test_default_log(self):
        def test():
            combo_graph = Graph(Data())
            list(combo_graph.variants(self.b2_id, variant_limit=0))
        self.assertRaises(Exception, test)

    def test_card_limit(self):
        combo_graph = Graph(Data(), log=lambda _: None)
        self.maxDiff = None
        self.assertCountEqual(combo_graph.variants(self.b2_id, card_limit=0), [])
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertCountEqual(combo_graph.variants(self.b2_id, card_limit=1), [])
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertCountEqual(combo_graph.variants(self.b2_id, card_limit=2), [])
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertEqual(len(list(combo_graph.variants(self.b2_id, card_limit=3))), 1)
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertEqual(len(list(combo_graph.variants(self.b2_id, card_limit=4))), 2)
        combo_graph = Graph(Data(), log=lambda _: None)
        self.assertEqual(len(list(combo_graph.variants(self.b2_id, card_limit=5))), 3)
