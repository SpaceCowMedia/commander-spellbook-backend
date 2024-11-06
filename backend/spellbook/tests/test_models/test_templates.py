from django.test import TestCase
from spellbook.tests.testing import TestCaseMixinWithSeeding
from common.inspection import count_methods
from spellbook.models import Template
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH


class TemplateTests(TestCaseMixinWithSeeding, TestCase):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')
        self.assertEqual(t.description, 'hello.')

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
        self.assertTrue(t.scryfall_link(raw=True).startswith('http'))
        self.assertIn(t.scryfall_link(raw=True), t.scryfall_link(raw=False))

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link())
        self.assertNotIn(t.query_string(), t.scryfall_link())
        self.assertNotIn('<a', t.scryfall_link())
        self.assertNotIn('target="_blank"', t.scryfall_link())

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)
