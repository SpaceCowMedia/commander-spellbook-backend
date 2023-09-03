from urllib.parse import quote_plus
from django.utils import timezone
from django.contrib.auth.models import User
from common.inspection import count_methods
from .abstract_test import AbstractModelTests
from spellbook.models import Card, Feature, Template, Combo, Job, IngredientInCombination, Variant, VariantSuggestion
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH
from spellbook.utils import launch_job_command
from spellbook.models import id_from_cards_and_templates_ids
from django.core.exceptions import ValidationError


class CardTests(AbstractModelTests):
    def test_card_fields(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(c.name, 'A A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.legal)
        self.assertFalse(c.spoiler)

    def test_query_string(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertEqual(f'q=%21%22{quote_plus(c.name)}%22', c.query_string())

    def test_scryfall_link(self):
        c = Card.objects.get(id=self.c1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, c.scryfall_link())
        self.assertIn(c.query_string(), c.scryfall_link())
        self.assertIn('<a', c.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 3)

    def test_name_unaccented(self):
        c = Card.objects.create(name='à, è, ì, ò, ù, y, À, È, Ì, Ò, Ù, Y, á, é, í, ó, ú, ý, Á, É, Í, Ó, Ú, Ý, â, ê, î, ô, û, y, Â, Ê, Î, Ô, Û, Y, ä, ë, ï, ö, ü, ÿ, Ä, Ë, Ï, Ö, Ü, Ÿ', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')
        self.assertEqual(c.name_unaccented, ', '.join('aeiouyAEIOUY' * 4))
        c.name = 'àààèèèìììòòòùùù'
        c.save()
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')
        c.name = 'ààèèììòòùù'
        Card.objects.bulk_update([c], ['name', 'name_unaccented'])
        c.refresh_from_db()
        self.assertEqual(c.name_unaccented, 'aaeeiioouu')
        c.delete()
        Card.objects.bulk_create([Card(name='àààèèèìììòòòùùù', oracle_id='47d6f04b-a6fe-4274-bd27-888475158e82')])
        c = Card.objects.get(name='àààèèèìììòòòùùù')
        self.assertEqual(c.name_unaccented, 'aaaeeeiiiooouuu')


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
        self.assertTrue(t.query_string().startswith('q='))

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
        self.assertEqual(c.kind, Combo.Kind.GENERATOR)
        self.assertEqual(c.cardincombo_set.count(), 2)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000002').zone_locations, IngredientInCombination.ZoneLocation.HAND)
        self.assertEqual(c.cardincombo_set.get(card__oracle_id='00000000-0000-0000-0000-000000000003').zone_locations, IngredientInCombination.ZoneLocation.BATTLEFIELD)
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
        self.assertEqual(c.kind, Combo.Kind.GENERATOR)
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
        c = Combo.objects.get(id=self.b1_id)
        for card in c.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', c.query_string())
        self.assertIn('+or+', c.query_string())
        self.assertTrue(c.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 3)


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
        v = Variant.objects.get(id=self.v1_id)
        for card in v.uses.all():
            self.assertIn(f'%21%22{quote_plus(card.name)}%22', v.query_string())
        self.assertIn('+or+', v.query_string())
        self.assertTrue(v.query_string().startswith('q='))

    def test_method_count(self):
        self.assertEqual(count_methods(Variant), 3)


class VariantSuggestionTests(AbstractModelTests):
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

    def test_method_count(self):
        self.assertEqual(count_methods(VariantSuggestion), 2)

    def test_validate_against_redundancy(self):
        s1 = VariantSuggestion.objects.get(id=self.s1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(s1.uses.values_list('card', flat=True)),
            list(s1.requires.values_list('template', flat=True))))

    def test_validate_against_already_present(self):
        launch_job_command('generate_variants', None)
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        self.assertRaises(ValidationError, lambda: VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)),
            list(v1.requires.values_list('name', flat=True))))

    def test_validate_success(self):
        launch_job_command('generate_variants', None)
        self.v1_id = id_from_cards_and_templates_ids([self.c8_id, self.c1_id], [self.t1_id])
        v1 = Variant.objects.get(id=self.v1_id)
        VariantSuggestion.validate(
            list(v1.uses.values_list('name', flat=True)[:1]),
            list(v1.requires.values_list('name', flat=True)))
