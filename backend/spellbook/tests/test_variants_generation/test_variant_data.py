from dataclasses import fields

from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from spellbook.variants.variant_data import (
    Data, VariantRow, CardInVariantRow, TemplateInVariantRow,
    FeatureProducedByVariantRow, VariantOfComboRow, VariantIncludesComboRow,
)
from spellbook.models import CardInVariant, FeatureOfCard, TemplateInVariant, Variant, Combo, Feature, Card, Template


def row_from_instance(row_class, instance):
    return row_class(*(getattr(instance, field.name) for field in fields(row_class)))


def card_in_variant_row(card_in_variant: CardInVariant) -> CardInVariantRow:
    return row_from_instance(CardInVariantRow, card_in_variant)


def template_in_variant_row(template_in_variant: TemplateInVariant) -> TemplateInVariantRow:
    return row_from_instance(TemplateInVariantRow, template_in_variant)


class VariantDataTests(SpellbookTestCaseWithSeeding):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_variants()

    def test_combos(self):
        data = Data()
        base = Combo.objects.all()
        query = base.filter(status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY))
        self.assertEqual(len(data.id_to_combo), base.count())
        self.assertDictEqual(data.id_to_combo, {c.id: c for c in base})
        base = FeatureOfCard.objects.all()
        self.assertEqual(len(data.id_to_feature_of_card), base.count())
        self.assertDictEqual(data.id_to_feature_of_card, {f.id: f for f in base})
        self.assertEqual(set(c.id for c in data.generator_combos), set(Combo.objects.filter(status=Combo.Status.GENERATOR).values_list('id', flat=True)))
        self.assertDictEqual({k: data.combo_to_cards[k] for k in query.values_list('id', flat=True)}, {combo.id: list(combo.cardincombo_set.all()) for combo in query.all()})
        self.assertDictEqual({k: data.combo_to_templates[k] for k in query.values_list('id', flat=True)}, {combo.id: list(combo.templateincombo_set.all()) for combo in query.all()})
        self.assertDictEqual({k: data.combo_to_produced_features[k] for k in query.values_list('id', flat=True)}, {combo.id: list(combo.featureproducedincombo_set.all()) for combo in query.all()})
        self.assertDictEqual({k: data.combo_to_needed_features[k] for k in query.values_list('id', flat=True)}, {combo.id: list(combo.featureneededincombo_set.all()) for combo in query.all()})
        self.assertDictEqual({k: data.combo_to_removed_features[k] for k in query.values_list('id', flat=True)}, {combo.id: list(combo.featureremovedincombo_set.all()) for combo in query.all()})

    def test_cards(self):
        data = Data()
        self.assertEqual(set(c.id for c in data.id_to_card.values()), set(Card.objects.values_list('id', flat=True)))
        self.assertDictEqual({k: data.card_to_features[k] for k in Card.objects.values_list('id', flat=True)}, {card.id: list(card.featureofcard_set.all()) for card in Card.objects.all()})
        self.assertDictEqual(data.id_to_card, {c.id: c for c in Card.objects.all()})

    def test_templates(self):
        data = Data()
        self.assertEqual(set(t.id for t in data.id_to_template.values()), set(Template.objects.values_list('id', flat=True)))
        self.assertDictEqual(data.id_to_template, {t.id: t for t in Template.objects.all()})

    def test_features(self):
        data = Data()
        self.assertEqual(set(f.id for f in data.id_to_feature.values()), set(Feature.objects.values_list('id', flat=True)))
        self.assertEqual(data.id_to_feature, {f.id: f for f in Feature.objects.all()})

    def test_utility_features_ids(self):
        data = Data()
        self.assertSetEqual(data.utility_features_ids, set(Feature.objects.filter(status__in=(Feature.Status.HIDDEN_UTILITY, Feature.Status.PUBLIC_UTILITY)).values_list('id', flat=True)))

    def test_variants(self):
        v: Variant = Variant.objects.first()  # type: ignore
        v.status = Variant.Status.NOT_WORKING
        v.save()
        data = Data()
        self.assertEqual(set(v.id for v in data.id_to_variant.values()), set(Variant.objects.values_list('id', flat=True)))
        self.assertDictEqual(data.id_to_variant, {v.id: VariantRow(v.id, v.status, v.name) for v in Variant.objects.all()})
        self.assertDictEqual(data.variant_to_cards, {v.id: set(map(card_in_variant_row, v.cardinvariant_set.all())) for v in Variant.objects.all()})
        self.assertDictEqual(data.variant_to_templates, {v.id: set(map(template_in_variant_row, v.templateinvariant_set.all())) for v in Variant.objects.all()})
        self.assertDictEqual(data.variant_to_of_sets, {v.id: {VariantOfComboRow(of.id, of.combo_id, of.variant_id) for of in v.variantofcombo_set.all()} for v in Variant.objects.all()})
        self.assertDictEqual(data.variant_to_includes_sets, {v.id: {VariantIncludesComboRow(i.id, i.combo_id, i.variant_id) for i in v.variantincludescombo_set.all()} for v in Variant.objects.all()})
        self.assertDictEqual(data.variant_to_produces, {v.id: {FeatureProducedByVariantRow(p.id, p.feature_id, p.variant_id, p.quantity) for p in v.featureproducedbyvariant_set.all()} for v in Variant.objects.all()})

    def test_card_variant_dict(self):
        data = Data()
        for card_id, variant_id in data.variant_uses_card_dict.keys():
            self.assertIn(card_id, set(Variant.objects.get(pk=variant_id).uses.all().values_list('id', flat=True)))

    def test_template_variant_dict(self):
        data = Data()
        for template_id, variant_id in data.variant_requires_template_dict.keys():
            self.assertIn(template_id, set(Variant.objects.get(pk=variant_id).requires.all().values_list('id', flat=True)))

    def test_fetch_variants(self):
        data = Data()
        ids = list(data.id_to_variant.keys())
        instances = data.fetch_variants(ids)
        self.assertEqual(set(instances.keys()), set(ids))
        for id, instance in instances.items():
            self.assertIsInstance(instance, Variant)
            self.assertEqual(instance.id, id)

    def test_number_of_queries(self):
        with self.assertNumQueries(21):
            Data()
