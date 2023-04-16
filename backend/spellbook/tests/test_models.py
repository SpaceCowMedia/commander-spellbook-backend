from django.utils import timezone
from django.contrib.auth.models import User
from .inspection import count_methods
from .abstract_test import AbstractModelTests
from spellbook.models import Card, Feature, Template, Combo, Job, IngredientInCombination, Variant
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH
from spellbook.utils import launch_job_command
from spellbook.variants.variants_generator import id_from_cards_and_templates_ids


class CardTests(AbstractModelTests):
    def test_card_fields(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.name, 'A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.legal)
        self.assertFalse(c.spoiler)

    def test_query_string(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.query_string(), 'q=%21%22A%22')

    def test_scryfall_link(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, c.scryfall_link())
        self.assertIn(c.query_string(), c.scryfall_link())
        self.assertIn('<a', c.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 2)


class FeatureTests(AbstractModelTests):
    def test_feature_fields(self):
        f = Feature.objects.get(id=self.f1_id)
        self.assertEqual(f.name, 'FA')
        self.assertEqual(f.description, 'Feature A')
        self.assertEqual(f.cards.count(), 1)
        self.assertTrue(f.utility)
        f = Feature.objects.get(id=self.f2_id)
        self.assertFalse(f.utility)

    def test_method_count(self):
        self.assertEqual(count_methods(Feature), 1)


class TemplateTests(AbstractModelTests):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')

    def test_query_string(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn('q=tou%3E5', t.query_string())

    def test_scryfall_api_url(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_API_ROOT, t.scryfall_api())
        self.assertIn(t.query_string(), t.scryfall_api())

    def test_scryfall_link(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertIn(t.query_string(), t.scryfall_link())
        self.assertIn('<a', t.scryfall_link())
        self.assertIn('target="_blank"', t.scryfall_link())

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertNotIn(t.query_string(), t.scryfall_link())
        self.assertNotIn('<a', t.scryfall_link())
        self.assertNotIn('target="_blank"', t.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)


class ComboTests(AbstractModelTests):
    def test_combo_fields(self):
        c = Combo.objects.get(id=self.b1_id)
        self.assertEqual(c.description, '1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertFalse(c.generator)
        self.assertEqual(c.cardincombo_set.count(), 2)
        self.assertEqual(c.cardincombo_set.get(card__name='B').zone_locations, IngredientInCombination.ZoneLocation.HAND)
        self.assertEqual(c.cardincombo_set.get(card__name='C').zone_locations, IngredientInCombination.ZoneLocation.BATTLEFIELD)
        self.assertEqual(c.templateincombo_set.count(), 0)
        c = Combo.objects.get(id=self.b2_id)
        self.assertEqual(c.description, '2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertTrue(c.generator)
        self.assertEqual(c.cardincombo_set.count(), 0)
        self.assertEqual(c.templateincombo_set.count(), 1)
        self.assertEqual(c.templateincombo_set.get(template__name='TA').zone_locations, IngredientInCombination.ZoneLocation.GRAVEYARD)

    def test_ingredients(self):
        for c in Combo.objects.all():
            cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
            self.assertEqual(list(c.cards()), list(map(lambda x: x.card, cic)))
            tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
            self.assertEqual(list(c.templates()), list(map(lambda x: x.template, tic)))

    def test_query_string(self):
        c = Combo.objects.get(id=self.c1_id)
        self.assertIn('%21%22B%22', c.query_string())
        self.assertIn('%21%22C%22', c.query_string())
        self.assertIn('+or+', c.query_string())

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 4)


class JobTests(AbstractModelTests):
    def setUp(self):
        super().setUp()
        User.objects.create_user(username='test', password='test', is_staff=True)

    def test_start(self):
        u = User.objects.get(username='test')
        j = Job.start('job name', timezone.timedelta(minutes=5), user=u)
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'job name')
        self.assertEqual(j.started_by, u)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)

    def test_start_without_duration(self):
        Job.objects.bulk_create([
            Job(
                name='a job name',
                status=Job.Status.SUCCESS,
                expected_termination=timezone.now() + timezone.timedelta(minutes=10),
                termination=timezone.now() + timezone.timedelta(minutes=5)),
        ])
        j = Job.start('a job name')
        self.assertIsNotNone(j)
        self.assertEqual(j.name, 'a job name')
        self.assertIsNone(j.started_by)
        self.assertEqual(j.status, Job.Status.PENDING)
        self.assertIsNotNone(j.expected_termination)
        self.assertGreater(j.expected_termination, timezone.now() + timezone.timedelta(minutes=5))

    def test_method_count(self):
        self.assertEqual(count_methods(Job), 2)


class VariantTests(AbstractModelTests):
    def setUp(self):
        super().setUp()
        launch_job_command('generate_variants', None)
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        self.v2_id = id_from_cards_and_templates_ids([self.c3_id, self.c1_id, self.c2_id], [self.t1_id])
        self.v3_id = id_from_cards_and_templates_ids([self.c5_id, self.c6_id, self.c2_id, self.c3_id], [self.t1_id])
        self.v4_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [])

    def test_variant_fields(self):
        v = Variant.objects.get(id=self.v1_id)
        self.assertSetEqual(set(v.uses.values_list('id', flat=True)), {self.c8_id, self.c1_id})
        self.assertSetEqual(set(v.cards().values_list('id', flat=True)), {self.c8_id, self.c1_id})
        self.assertSetEqual(set(v.requires.values_list('id', flat=True)), {self.t1_id})
        self.assertSetEqual(set(v.templates().values_list('id', flat=True)), {self.t1_id})
        self.assertSetEqual(set(v.produces.values_list('id', flat=True)), {self.f4_id, self.f2_id})
        self.assertSetEqual(set(v.includes.values_list('id', flat=True)), {self.b4_id, self.b2_id})
        self.assertSetEqual(set(v.of.values_list('id', flat=True)), {self.b2_id})
        self.assertEqual(v.status, Variant.Status.NEW)
        self.assertIn('{U}{U}', v.mana_needed)
        self.assertIn('{R}{R}', v.mana_needed)
        self.assertIn('Some requisites.', v.other_prerequisites)
        self.assertIn('2', v.description)
        self.assertIn('4', v.description)
        self.assertEqual(v.identity, 'W')
        self.assertEqual(v.generated_by.id, Job.objects.get(name='generate_variants').id)
        self.assertEqual(v.legal, True)
        self.assertEqual(v.spoiler, False)

    def test_ingredients(self):
        for v in Variant.objects.all():
            civ = sorted(v.cardinvariant_set.all(), key=lambda x: x.order)
            self.assertEqual(list(v.cards()), list(map(lambda x: x.card, civ)))
            tiv = sorted(v.templateinvariant_set.all(), key=lambda x: x.order)
            self.assertEqual(list(v.templates()), list(map(lambda x: x.template, tiv)))

    def test_query_string(self):
        c = Variant.objects.get(id=self.v1_id)
        self.assertIn('%21%22A%22', c.query_string())
        self.assertIn('%21%22H%22', c.query_string())
        self.assertIn('+or+', c.query_string())

    def test_method_count(self):
        self.assertEqual(count_methods(Variant), 3)
