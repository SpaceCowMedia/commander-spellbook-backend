from spellbook.models import Combo
from spellbook.variants.variant_data import Data
from spellbook.variants.combo_graph import Graph
from spellbook.tests.abstract_test import AbstractModelTests


class ComboGraphTest(AbstractModelTests):
    def setUp(self) -> None:
        super().setUp()
        super().generate_variants()

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

    def test_replacements(self):
        combo_graph = Graph(Data())
        variants = list(combo_graph.variants(self.b2_id))
        for variant in variants:
            card_ids = {c for c in variant.cards}
            template_ids = {t for t in variant.templates}
            replacements = variant.replacements
            for replacement_values in replacements.values():
                self.assertGreaterEqual(len(replacement_values), 1)
                for replacement_value in replacement_values:
                    cards = replacement_value.cards
                    templates = replacement_value.templates
                    replacement_card_ids = {c for c in cards}
                    replacement_template_ids = {t for t in templates}
                    self.assertTrue(card_ids.issuperset(replacement_card_ids))
                    self.assertTrue(template_ids.issuperset(replacement_template_ids))
