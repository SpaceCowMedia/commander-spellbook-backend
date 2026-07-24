from django.core.exceptions import ValidationError
from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, Combo, CardInCombo, ZoneLocation
from urllib.parse import quote_plus


class ComboTests(SpellbookTestCaseWithSeeding):
    def test_used_face_validation(self):
        single = Card.objects.create(name='Single Face Card', type_line='Instant')
        dfc = Card.objects.create(name='Front // Back', type_line='Creature // Creature', faces=2)
        combo = Combo.objects.create(status=Combo.Status.UTILITY)
        # A used face on a single-faced card is not allowed
        cic_single = CardInCombo(card=single, combo=combo, order=1, zone_locations=ZoneLocation.HAND, used_face=1)
        with self.assertRaises(ValidationError):
            cic_single.clean()
        # A used face beyond the number of faces is not allowed
        cic_out_of_range = CardInCombo(card=dfc, combo=combo, order=2, zone_locations=ZoneLocation.BATTLEFIELD, used_face=3)
        with self.assertRaises(ValidationError):
            cic_out_of_range.clean()
        # A valid used face on a multi-faced card, as well as a blank one, are allowed
        CardInCombo(card=dfc, combo=combo, order=3, zone_locations=ZoneLocation.BATTLEFIELD, used_face=2).clean()
        CardInCombo(card=dfc, combo=combo, order=4, zone_locations=ZoneLocation.BATTLEFIELD, used_face=None).clean()
        CardInCombo(card=single, combo=combo, order=5, zone_locations=ZoneLocation.HAND, used_face=None).clean()

    def test_combo_fields(self):
        c = Combo.objects.get(id=self.b1_id)
        self.assertEqual(c.description, 'a1')
        self.assertEqual(c.comment, '***1')
        self.assertEqual(c.notes, 'aa1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.is_mana_needed_an_accurate_minimum, True)
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
        self.assertEqual(c.comment, '***2')
        self.assertEqual(c.notes, 'bb2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.is_mana_needed_an_accurate_minimum, True)
        self.assertEqual(c.easy_prerequisites, 'Some easy requisites.')
        self.assertEqual(c.notable_prerequisites, 'Some notable requisites.')
        self.assertEqual(c.status, Combo.Status.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 0)
        self.assertEqual(c.templateincombo_set.count(), 1)
        self.assertEqual(c.templateincombo_set.get(template__name='TA').zone_locations, ZoneLocation.GRAVEYARD)
        self.assertEqual(c.allow_many_cards, False)
        self.assertEqual(c.allow_multiple_copies, False)

    def test_recipe(self):
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
            self.assertDictEqual(c.features_removed(), {f.feature.name: 1 for f in c.featureremovedincombo_set.all()})

    def test_query_string(self):
        c = Combo.objects.get(id=self.b1_id)
        for card in c.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', c.query_string())
        self.assertIn('+or+', c.query_string())
        self.assertTrue(c.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 6)

    def test_special_characters_in_description(self):
        c = Combo.objects.create(description='Ratonhnhaké:ton', is_mana_needed_an_accurate_minimum=True)
        c.full_clean()
