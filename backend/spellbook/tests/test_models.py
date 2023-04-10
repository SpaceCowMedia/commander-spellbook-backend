from datetime import datetime
from django.test import TestCase
from django.conf import settings
from .populate_db import populate_db
from .inspection import count_methods
from spellbook.models import Card, Feature, Template, Combo, Job, Variant
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH
from spellbook.utils import launch_job_command


class AbstractModelTests(TestCase):
    def setUp(self) -> None:
        populate_db()
        settings.ASYNC_GENERATION = False


class CardTests(AbstractModelTests):
    def test_card_fields(self):
        c = Card.objects.get(name='A')
        self.assertEqual(c.name, 'A')
        self.assertEqual(str(c.oracle_id), '00000000-0000-0000-0000-000000000001')
        self.assertEqual(c.features.count(), 1)
        self.assertEqual(c.identity, 'W')
        self.assertTrue(c.legal)
        self.assertFalse(c.spoiler)

    def test_card_query_string(self):
        c = Card.objects.get(name='A')
        self.assertEqual(c.query_string(), 'q=%21%22A%22')

    def test_method_count(self):
        self.assertEqual(count_methods(Card), 2)


class FeatureTests(AbstractModelTests):
    def test_feature_fields(self):
        f = Feature.objects.get(name='FA')
        self.assertEqual(f.name, 'FA')
        self.assertEqual(f.description, 'Feature A')
        self.assertEqual(f.cards.count(), 1)
        self.assertFalse(f.utility)

    def test_method_count(self):
        self.assertEqual(count_methods(Feature), 1)


class TemplateTests(AbstractModelTests):
    def test_template(self):
        t = Template.objects.get(name='TA')
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')

    def test_query_string(self):
        t = Template.objects.get(name='TA')
        self.assertIn('q=tou%3E5', t.query_string())

    def test_scryfall_api_url(self):
        t = Template.objects.get(name='TA')
        self.assertIn(SCRYFALL_API_ROOT, t.scryfall_api())
        self.assertIn(t.query_string(), t.scryfall_api())

    def test_scryfall_link(self):
        t = Template.objects.get(name='TA')
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
        c = Combo.objects.get(description='1')
        self.assertEqual(c.description, '1')
        self.assertEqual(c.uses.count(), 2)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 0)
        self.assertEqual(c.produces.count(), 2)
        self.assertEqual(c.removes.count(), 0)
        self.assertEqual(c.mana_needed, '{W}{W}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertFalse(c.generator)
        cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
        self.assertEqual(list(c.cards()), list(map(lambda x: x.card, cic)))
        tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
        self.assertEqual(list(c.templates()), list(map(lambda x: x.template, tic)))
        c = Combo.objects.get(description='2')
        self.assertEqual(c.description, '2')
        self.assertEqual(c.uses.count(), 0)
        self.assertEqual(c.needs.count(), 1)
        self.assertEqual(c.requires.count(), 1)
        self.assertEqual(c.produces.count(), 1)
        self.assertEqual(c.removes.count(), 1)
        self.assertEqual(c.mana_needed, '{U}{U}')
        self.assertEqual(c.other_prerequisites, 'Some requisites.')
        self.assertTrue(c.generator)
        cic = sorted(c.cardincombo_set.all(), key=lambda x: x.order)
        self.assertEqual(list(c.cards()), list(map(lambda x: x.card, cic)))
        tic = sorted(c.templateincombo_set.all(), key=lambda x: x.order)
        self.assertEqual(list(c.templates()), list(map(lambda x: x.template, tic)))

    def test_method_count(self):
        self.assertEqual(count_methods(Combo), 4)


class JobTests(AbstractModelTests):
    def clean_jobs_job(self):
        j = Job(
            name='test',
            expected_termination=datetime.fromtimestamp(1681126064),
            status=Job.Status.PENDING)
        j.save()
        j2 = Job(
            name='test2',
            expected_termination=datetime.fromtimestamp(1681126064),
            termination=datetime.fromtimestamp(1681126065),
            status=Job.Status.SUCCESS)
        j2.save()
        result = launch_job_command('clean_jobs', None)
        self.assertTrue(result)
        self.assertEqual(Job.objects.count(), 2)
        cleaned = Job.objects.get(name='test')
        self.assertEqual(cleaned.status, Job.Status.FAILURE)
        self.assertIsNotNone(cleaned.termination)
        self.assertEqual(Job.objects.get(name='test2').status, Job.Status.SUCCESS)

    def test_export_variants(self):
        pass  # TODO: Implement

    def test_generate_variants(self):
        pass  # TODO: Implement

    def test_method_count(self):
        self.assertEqual(count_methods(Job), 2)
