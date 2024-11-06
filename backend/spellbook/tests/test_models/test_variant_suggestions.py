from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, CardUsedInVariantSuggestion, Feature, Template, Variant, VariantSuggestion, ZoneLocation, id_from_cards_and_templates_ids
from django.core.exceptions import ValidationError


class VariantSuggestionTests(TestCaseMixinWithSeeding, TestCase):
    def test_variant_suggestion_fields(self):
        s = VariantSuggestion.objects.get(id=self.s1_id)
        card_names = {Card.objects.get(id=self.c1_id).name, Card.objects.get(id=self.c2_id).name}
        template_names = {Template.objects.get(id=self.t1_id).name}
        feature_names = {Feature.objects.get(id=self.f1_id).name}
        self.assertSetEqual(set(s.uses.values_list('card', flat=True)), card_names)
        self.assertSetEqual(set(s.requires.values_list('template', flat=True)), template_names)
        self.assertSetEqual(set(s.produces.values_list('feature', flat=True)), feature_names)
        self.assertEqual(s.status, VariantSuggestion.Status.NEW)
        self.assertEqual('{W}{W}', s.mana_needed)
        self.assertEqual('Some requisites.', s.other_prerequisites)
        self.assertEqual('1', s.description)
        self.assertEqual(s.suggested_by, None)
        self.assertTrue(s.spoiler)

    def test_ingredients(self):
        for s in VariantSuggestion.objects.all():
            civ = sorted(s.uses.all(), key=lambda x: x.order)
            self.assertDictEqual(s.cards(), {ci.card: ci.quantity for ci in civ})
            tiv = sorted(s.requires.all(), key=lambda x: x.order)
            self.assertDictEqual(s.templates(), {ti.template: ti.quantity for ti in tiv})
            self.assertDictEqual(s.features_produced(), {f.feature: 1 for f in s.produces.all()})
            self.assertDictEqual(s.features_needed(), {})

    def test_method_count(self):
        self.assertEqual(count_methods(VariantSuggestion), 4)

    def test_validate_against_redundancy(self):
        s1 = VariantSuggestion.objects.get(id=self.s1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(s1.uses.values_list('card', flat=True)),
            list(s1.requires.values_list('template', flat=True)),
            ['result']))

    def test_validate_against_already_present(self):
        super().generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)),
            list(v1.requires.values_list('name', flat=True)),
            ['result']))

    def test_validate_against_empty_results(self):
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            ['a'],
            ['b'],
            []))

    def test_validate_against_empty_cards(self):
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            [],
            ['b'],
            ['result']))

    def test_validate_success(self):
        super().generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)[:1]),
            list(v1.requires.values_list('name', flat=True)),
            ['result'])

    def test_card_in_variant_suggestion_validation(self):
        s = VariantSuggestion.objects.get(id=self.s1_id)
        c = CardUsedInVariantSuggestion(card='A card', variant=s, order=1, zone_locations=ZoneLocation.COMMAND_ZONE)
        self.assertRaises(ValidationError, lambda: c.full_clean())
