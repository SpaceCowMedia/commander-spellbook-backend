from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Combo, ZoneLocation
from urllib.parse import quote_plus


class ComboTests(TestCaseMixinWithSeeding, TestCase):
    def test_combo_fields(self):
        c = Combo.objects.get(id=self.b1_id)
        self.assertEqual(c.description, 'a1')
        self.assertEqual(c.notes, '***1')
        self.assertEqual(c.public_notes, 'aa1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.easy_prerequisites, 'Some easy requisites.')
        self.assertEqual(c.notable_prerequisites, 'Some notable requisites.')
        self.assertEqual(c.status, Combo.Status.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 2)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000002').zone_locations, ZoneLocation.HAND)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000003').zone_locations, ZoneLocation.BATTLEFIELD)
        self.assertEqual(c.templateincombo_set.count(), 0)
        self.assertEqual(c.allow_many_cards, False)
        self.assertEqual(c.allow_multiple_copies, False)
        c = Combo.objects.get(id=self.b2_id)
        self.assertEqual(c.description, 'b2')
        self.assertEqual(c.notes, '***2')
        self.assertEqual(c.public_notes, 'bb2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.easy_prerequisites, '')
        self.assertEqual(c.notable_prerequisites, 'Some requisites.')
        self.assertEqual(c.status, Combo.Status.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 0)
        self.assertEqual(c.templateincombo_set.count(), 1)
        self.assertEqual(c.templateincombo_set.get(template__name='TA').zone_locations, ZoneLocation.GRAVEYARD)
        self.assertEqual(c.allow_many_cards, False)
        self.assertEqual(c.allow_multiple_copies, False)

    def test_ingredients(self):
        for c in Combo.objects.all():
            cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
            self.assertDictEqual(c.cards(), {ci.card.name: ci.quantity for ci in cic})
            tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
            self.assertDictEqual(c.templates(), {ti.template.name: ti.quantity for ti in tic})
            features_needed = dict[str, int]()
            for f in c.featureneededincombo_set.all():
                features_needed[f.feature.name] = features_needed.get(f.feature.name, 0) + f.quantity
            self.assertDictEqual(c.features_needed(), features_needed)
            self.assertDictEqual(c.features_produced(), {f.feature.name: 1 for f in c.featureproducedincombo_set.all()})

    def test_query_string(self):
        c = Combo.objects.get(id=self.b1_id)
        for card in c.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', c.query_string())
        self.assertIn('+or+', c.query_string())
        self.assertTrue(c.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 4)
