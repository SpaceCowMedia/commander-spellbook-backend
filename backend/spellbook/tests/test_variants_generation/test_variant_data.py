from spellbook.tests.abstract_test import AbstractModelTests
from spellbook.variants.variant_data import Data, debug_queries
from spellbook.models import Variant, Combo, Feature, Card, Template, id_from_cards_and_templates_ids
from spellbook.utils import launch_job_command


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
