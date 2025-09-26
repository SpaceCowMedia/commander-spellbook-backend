from spellbook.tests.testing import SpellbookTestCaseWithSeeding
from common.inspection import count_methods
from spellbook.models import Card, Template
from spellbook.models.scryfall import SCRYFALL_API_ROOT, SCRYFALL_WEBSITE_CARD_SEARCH


class TemplateTests(SpellbookTestCaseWithSeeding):
    def test_template_fields(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertEqual(t.name, 'TA')
        self.assertEqual(t.scryfall_query, 'tou>5')
        self.assertEqual(t.description, 'hello.')

    def test_query_string(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn('tou%3E5', t.query_string() or '')
        self.assertIn('legal%3Acommander', t.query_string() or '')
        self.assertTrue((t.query_string() or '').startswith('q='))

    def test_scryfall_api_url(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_API_ROOT, t.scryfall_api() or '')
        self.assertIn(t.query_string(), t.scryfall_api() or '')

    def test_scryfall_link(self):
        t = Template.objects.get(id=self.t1_id)
        self.assertIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link() or '')
        self.assertIn(t.query_string(), t.scryfall_link() or '')
        self.assertIn('<a', t.scryfall_link() or '')
        self.assertIn('target="_blank"', t.scryfall_link() or '')
        self.assertTrue((t.scryfall_link(raw=True) or '').startswith('http'))
        self.assertIn(t.scryfall_link(raw=True), t.scryfall_link(raw=False) or '')

        t.scryfall_query = ''
        self.assertNotIn(SCRYFALL_WEBSITE_CARD_SEARCH, t.scryfall_link() or '')
        self.assertNotIn(t.query_string(), t.scryfall_link() or '')
        self.assertNotIn('<a', t.scryfall_link() or '')
        self.assertNotIn('target="_blank"', t.scryfall_link() or '')

    def test_card_replacements(self):
        t = Template.objects.get(id=self.t2_id)
        self.assertEqual(t.replacements.count(), 1)
        self.assertEqual(t.scryfall_link(), None)
        t.replacements.add(Card.objects.get(id=self.c4_id))
        self.assertEqual(t.replacements.count(), 2)

    def test_method_count(self):
        self.assertEqual(count_methods(Template), 4)
