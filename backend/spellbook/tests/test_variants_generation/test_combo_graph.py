from spellbook.models import Combo
from spellbook.variants.variant_data import Data
from spellbook.variants.combo_graph import Graph
from spellbook.tests.abstract_test import AbstractModelTests


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
