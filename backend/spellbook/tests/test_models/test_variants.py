from django.test import TestCase
from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, PreSerializedSerializer, Template, Variant, CardInVariant, TemplateInVariant, FeatureProducedByVariant, Feature, ZoneLocation, estimate_bracket, id_from_cards_and_templates_ids
from spellbook.serializers import VariantSerializer
from decimal import Decimal
from urllib.parse import quote_plus


class VariantTests(SpellbookTestCaseWithSeeding):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.generate_variants()
        cls.v1_id = id_from_cards_and_templates_ids([cls.c8_id, cls.c1_id], [cls.t1_id])
        cls.v2_id = id_from_cards_and_templates_ids([cls.c3_id, cls.c1_id, cls.c2_id], [cls.t1_id])
        cls.v3_id = id_from_cards_and_templates_ids([cls.c5_id, cls.c6_id, cls.c2_id, cls.c3_id], [cls.t1_id])
        cls.v4_id = id_from_cards_and_templates_ids([cls.c8_id, cls.c1_id], [])

    def test_variant_fields(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        self.assertSetEqual(set(v.uses.values_list('id', flat=True)), {self.c8_id, self.c1_id})
        self.assertDictEqual(v.cards(), {Card.objects.get(pk=self.c8_id).name: 1, Card.objects.get(pk=self.c1_id).name: 1})
        self.assertSetEqual(set(v.requires.values_list('id', flat=True)), {self.t1_id})
        self.assertDictEqual(v.templates(), {Template.objects.get(pk=self.t1_id).name: 1})
        self.assertSetEqual(set(v.produces.values_list('id', flat=True)), {self.f4_id, self.f2_id})
        self.assertSetEqual(set(v.includes.values_list('id', flat=True)), {self.b4_id, self.b2_id})
        self.assertSetEqual(set(v.of.values_list('id', flat=True)), {self.b2_id})
        self.assertEqual(v.mana_value, 8)
        self.assertEqual(v.status, Variant.Status.NEW)
        self.assertIn('{U}{U}', v.mana_needed)
        self.assertIn('{R}{R}', v.mana_needed)
        self.assertEqual(v.is_mana_needed_an_accurate_minimum, False)
        self.assertIn('Some easy requisites.', v.easy_prerequisites)
        self.assertIn('Some notable requisites.', v.notable_prerequisites)
        self.assertIn('2', v.description)
        self.assertIn('2', v.comment)
        self.assertIn('2', v.notes)
        self.assertIn('4', v.description)
        self.assertIn('4', v.comment)
        self.assertIn('4', v.notes)
        self.assertEqual(v.identity, 'W')
        ids = set(Variant.objects.values_list('generated_by', flat=True))
        self.assertSetEqual(ids, {v.generated_by})
        self.assertEqual(v.legal_commander, True)
        self.assertEqual(v.spoiler, False)
        self.assertEqual(v.description_line_count, v.description.count('\n') + 1)
        self.assertEqual(v.prerequisites_line_count, v.easy_prerequisites.count('\n') + 1 + v.notable_prerequisites.count('\n') + 1)
        self.assertEqual(v.mana_value_needed, 4)
        self.assertEqual(v.popularity, None)
        self.assertIsNone(v.spellbook_link())

    def test_ingredients(self):
        for v in Variant.objects.all():
            civ = sorted(v.cardinvariant_set.all(), key=lambda x: x.order)
            self.assertDictEqual(v.cards(), {ci.card.name: ci.quantity for ci in civ})
            tiv = sorted(v.templateinvariant_set.all(), key=lambda x: x.order)
            self.assertDictEqual(v.templates(), {ti.template.name: ti.quantity for ti in tiv})

    def test_query_string(self):
        v = Variant.objects.get(id=self.v1_id)
        for card in v.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', v.query_string())
        self.assertIn('+or+', v.query_string())
        self.assertTrue(v.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Variant), 13)

    def test_update_variant_from_cards(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        cards = list(v.uses.all())
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        self.assertTrue(v.update_playable_fields(cards, requires_commander=True))
        non_commander_formats = (
            'vintage',
            'legacy',
            'modern',
            'pioneer',
            'standard',
            'pauper',
        )
        for f in non_commander_formats:
            self.assertFalse(getattr(v, f'legal_{f}'))
        self.assertTrue(v.legal_commander)
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertLess(len(v.identity), 5)
        c = Card(name='Extra card 1', oracle_id='00000000-0000-0000-0000-0000000000ff', identity='C')
        c.save()
        cards.append(c)
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        c.identity = 'WUBRG'
        c.save()
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        c.color = 'WUBRG'
        c.save()
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        c.spoiler = True
        c.save()
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        c.legal_predh = False
        c.save()
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))
        c.price_cardmarket = Decimal(100)
        c.save()
        self.assertTrue(v.update_playable_fields(cards, requires_commander=False))
        self.assertFalse(v.update_playable_fields(cards, requires_commander=False))

    def test_update_variant_from_recipe(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        recipe = v.get_recipe()
        self.assertFalse(v.update_variant_from_recipe(recipe))
        recipe.cards[0][1].identity = 'WUBRG'
        self.assertTrue(v.update_variant_from_recipe(recipe))
        self.assertFalse(v.update_variant_from_recipe(recipe))

    def test_update_variant(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        self.assertFalse(v.update_variant())
        c: Card = v.uses.first()  # type: ignore
        c.legal_commander = False
        c.save()
        self.assertTrue(v.update_variant())
        self.assertFalse(v.legal_commander)
        self.assertFalse(v.update_variant())

    def test_serialization(self):
        v = Variant.objects.get(id=self.v1_id)
        v.update_serialized(serializer=VariantSerializer)
        self.assertIsNotNone(v.serialized)
        self.assertIn('id', v.serialized)  # type: ignore
        self.assertFalse(Variant.serialized_objects.filter(id=self.v1_id).exists())
        v.save()
        self.assertTrue(Variant.serialized_objects.filter(id=self.v1_id).exists())
        v = Variant.serialized_objects.get(id=self.v1_id)
        self.assertIsNotNone(v.serialized)
        self.assertIn('id', v.serialized)  # type: ignore
        r = PreSerializedSerializer(v).data
        self.assertEqual(r, v.serialized)


class EstimateBracketTests(TestCase):
    def _make_recipe(self, cards=(), templates=(), notable_prerequisites=''):
        variant = Variant(notable_prerequisites=notable_prerequisites, mana_value_needed=0, is_mana_needed_an_accurate_minimum=True)
        civs = [
            (CardInVariant(card=card, quantity=quantity, zone_locations=ZoneLocation.BATTLEFIELD, must_be_commander=must_be_commander), card)
            for card, quantity, must_be_commander in cards
        ]
        tivs = [
            (TemplateInVariant(template=template, quantity=quantity, zone_locations=zone_locations, must_be_commander=must_be_commander), template)
            for template, quantity, zone_locations, must_be_commander in templates
        ]
        feature = Feature(name='Test Feature', status=Feature.Status.STANDALONE)
        fpbv = FeatureProducedByVariant(feature=feature, quantity=1)
        recipe = Variant.Recipe(cards=civs, templates=tivs, features=[(fpbv, feature)])
        return variant, recipe

    def test_commander_card_is_classified_as_arguable_not_sure(self):
        sure1 = Card(pk=1, name='Sure One', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        sure2 = Card(pk=2, name='Sure Two', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        commander = Card(pk=3, name='Commander Card', mana_value=3, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        variant, recipe = self._make_recipe(cards=[(sure1, 1, False), (sure2, 1, False), (commander, 1, False)])
        result = estimate_bracket(
            cards={sure1: 1, sure2: 1, commander: 1},
            templates={},
            included_variants=[(variant, recipe)],
        )
        combo = result.combos[0]
        self.assertFalse(combo.definitely_two_card)
        self.assertTrue(combo.arguably_two_card)

    def test_must_be_commander_template_is_classified_as_arguable_not_sure(self):
        sure1 = Card(pk=1, name='Sure One', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        sure2 = Card(pk=2, name='Sure Two', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        template = Template(pk=1, name='Commander Template', scryfall_query='o:test')
        variant, recipe = self._make_recipe(
            cards=[(sure1, 1, False), (sure2, 1, False)],
            templates=[(template, 1, ZoneLocation.COMMAND_ZONE, True)],
        )
        result = estimate_bracket(
            cards={sure1: 1, sure2: 1},
            templates={template: 1},
            included_variants=[(variant, recipe)],
        )
        combo = result.combos[0]
        self.assertFalse(combo.definitely_two_card)
        self.assertTrue(combo.arguably_two_card)

    def test_plain_template_is_classified_as_sure(self):
        sure1 = Card(pk=1, name='Sure One', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        template = Template(pk=1, name='Regular Template', scryfall_query='o:test')
        variant, recipe = self._make_recipe(
            cards=[(sure1, 1, False)],
            templates=[(template, 1, ZoneLocation.BATTLEFIELD, False)],
        )
        result = estimate_bracket(
            cards={sure1: 1},
            templates={template: 1},
            included_variants=[(variant, recipe)],
        )
        combo = result.combos[0]
        self.assertTrue(combo.definitely_two_card)

    def test_commander_in_provided_commanders_set_is_excluded_entirely(self):
        sure1 = Card(pk=1, name='Sure One', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        commander = Card(pk=2, name='Commander Card', mana_value=3, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        variant, recipe = self._make_recipe(cards=[(sure1, 1, False), (commander, 1, False)])
        result = estimate_bracket(
            cards={sure1: 1, commander: 1},
            templates={},
            included_variants=[(variant, recipe)],
            commanders={commander},
        )
        combo = result.combos[0]
        self.assertTrue(combo.definitely_two_card)

    def test_commander_eligible_card_not_in_commanders_set_is_classified_as_sure(self):
        sure1 = Card(pk=1, name='Sure One', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        sure2 = Card(pk=2, name='Sure Two', mana_value=1, legal_commander=True, type_line='Creature', oracle_text='')
        real_commander = Card(pk=3, name='Real Commander', mana_value=3, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        commander_eligible = Card(pk=4, name='Commander Eligible', mana_value=3, legal_commander=True, type_line='Legendary Creature - Human', oracle_text='')
        variant, recipe = self._make_recipe(cards=[(sure1, 1, False), (sure2, 1, False), (real_commander, 1, False), (commander_eligible, 1, False)])
        result = estimate_bracket(
            cards={sure1: 1, sure2: 1, real_commander: 1, commander_eligible: 1},
            templates={},
            included_variants=[(variant, recipe)],
            commanders={real_commander},
        )
        combo = result.combos[0]
        # With an explicit commanders set, the is_commander heuristic is disabled:
        # commander_eligible (not in the set) counts as a sure card, so the three
        # remaining sure cards make this neither a definite nor an arguable two-card combo.
        self.assertFalse(combo.definitely_two_card)
        self.assertFalse(combo.arguably_two_card)
