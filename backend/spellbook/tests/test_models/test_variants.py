from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, Job, PreSerializedSerializer, Template, Variant, id_from_cards_and_templates_ids
from spellbook.serializers import VariantSerializer
from decimal import Decimal
from urllib.parse import quote_plus


class VariantTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self):
        super().setUp()
        self.generate_variants()
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        self.v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        self.v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        self.v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])

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
        self.assertIn('Some requisites.', v.other_prerequisites)
        self.assertIn('2', v.description)
        self.assertIn('2', v.notes)
        self.assertIn('2', v.public_notes)
        self.assertIn('4', v.description)
        self.assertIn('4', v.notes)
        self.assertIn('4', v.public_notes)
        self.assertEqual(v.identity, 'W')
        self.assertEqual(v.generated_by.id, Job.objects.get(name='generate_variants').id)  # type: ignore
        self.assertEqual(v.legal_commander, True)
        self.assertEqual(v.spoiler, False)
        self.assertEqual(v.description_line_count, v.description.count('\n') + 1)
        self.assertEqual(v.other_prerequisites_line_count, v.other_prerequisites.count('\n') + 1)
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
        self.assertEqual(count_methods(Variant), 11)

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

    def test_update_variant_from_ingredients(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        civs = list((civ, civ.card) for civ in v.cardinvariant_set.all())
        tivs = list((tiv, tiv.template) for tiv in v.templateinvariant_set.all())
        fpvs = list((fpv, fpv.feature) for fpv in v.featureproducedbyvariant_set.all())
        self.assertFalse(v.update_variant_from_ingredients(civs, tivs, fpvs))
        civs[0][1].identity = 'WUBRG'
        self.assertTrue(v.update_variant_from_ingredients(civs, tivs, fpvs))
        self.assertFalse(v.update_variant_from_ingredients(civs, tivs, fpvs))

    def test_update_variant(self):
        v: Variant = Variant.objects.get(id=self.v1_id)
        self.assertFalse(v.update_variant())
        c: Card = v.uses.first()  # type: ignore
        c.legal_commander = False
        c.save()
        self.assertTrue(v.update_variant())
        self.assertFalse(v.legal_commander)
        self.assertFalse(v.update_variant())
        self.assertTrue(v.complete)
        for f in v.produces.all():
            f.relevant = False
            f.save()
        self.assertTrue(v.update_variant())
        self.assertFalse(v.complete)
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
