import os
from unittest import TestCase
from unittest.mock import patch, MagicMock
from bot_utils import (
    parse_queries, patch_query, url_from_query, summary_from_query, url_from_variant,
    compute_variant_name, compute_variant_recipe, uri_validator, SpellbookQuery
)


class TestBotUtils(TestCase):
    def test_parse_queries(self):
        text = 'This is a {{query1}} and another {{ query2 }} and {{}}.'
        result = parse_queries(text)
        self.assertEqual(result, ['query1', 'query2'])
        self.assertEqual(parse_queries('No queries here'), [])

    def test_patch_query(self):
        self.assertEqual(patch_query('foo'), 'foo format:commander')
        self.assertEqual(patch_query('legal:modern'), 'legal:modern')
        self.assertEqual(patch_query('banned:legacy'), 'banned:legacy')
        self.assertEqual(patch_query('format:legacy'), 'format:legacy')
        self.assertEqual(patch_query('foo format:commander'), 'foo format:commander')

    def test_url_from_query(self):
        with patch('bot_utils.patch_query', return_value='foo format:commander'):
            url = url_from_query('foo')
            self.assertTrue(url.startswith('/search?q='))
            self.assertIn('foo+format%3Acommander', url)

    def test_summary_from_query(self):
        summary = summary_from_query('foo', 'http://url')
        self.assertEqual(summary, '[`foo`](http://url)')

    @patch.dict(os.environ, {'SPELLBOOK_WEBSITE_URL': ''})
    def test_url_from_variant(self):
        variant = MagicMock()
        variant.id = '1234'
        url = url_from_variant(variant)
        self.assertEqual(url, '/combo/1234')

    def test_compute_variant_name(self):
        card1 = MagicMock()
        card1.quantity = 2
        card1.card.name = 'CardA'
        card2 = MagicMock()
        card2.quantity = 1
        card2.card.name = 'CardB'
        template1 = MagicMock()
        template1.quantity = 3
        template1.template.name = 'TemplateA'
        template2 = MagicMock()
        template2.quantity = 1
        template2.template.name = 'TemplateB'
        variant = MagicMock()
        variant.uses = [card1, card2]
        variant.requires = [template1, template2]
        name = compute_variant_name(variant)
        self.assertIn('2x CardA', name)
        self.assertIn('CardB', name)
        self.assertIn('3x TemplateA', name)
        self.assertIn('TemplateB', name)
        self.assertTrue(name.startswith('2x CardA + CardB + 3x TemplateA + TemplateB'))

    def test_compute_variant_recipe(self):
        # Test with <=4 produces
        variant = MagicMock()
        variant.uses = []
        variant.requires = []
        result1 = MagicMock()
        result1.feature.name = 'ResultA'
        result1.quantity = 2
        result2 = MagicMock()
        result2.feature.name = 'ResultB'
        result2.quantity = 1
        variant.produces = [result1, result2]
        with patch('bot_utils.compute_variant_name', return_value='NAME'):
            recipe = compute_variant_recipe(variant)
            self.assertTrue(recipe.startswith('NAME'))
            self.assertIn('ResultA', recipe)
            self.assertIn('ResultB', recipe)
            self.assertIn('➜', recipe)

        # Test with >4 produces
        variant.produces = []
        for i in range(6):
            feature = MagicMock()
            feature.name = f'R{i}'
            result = MagicMock()
            result.feature = feature
            result.quantity = 1
            variant.produces.append(result)
        with patch('bot_utils.compute_variant_name', return_value='NAME'):
            recipe = compute_variant_recipe(variant)
            self.assertTrue(recipe.endswith('...'))

    def test_uri_validator(self):
        self.assertTrue(uri_validator('https://example.com'))
        self.assertTrue(uri_validator('http://foo.bar'))
        self.assertFalse(uri_validator('not a url'))
        self.assertFalse(uri_validator('ftp:/missing.com'))
        self.assertFalse(uri_validator(''))

    def test_spellbook_query(self):
        with patch('bot_utils.patch_query', return_value='patched'), \
             patch('bot_utils.url_from_query', return_value='url'), \
             patch('bot_utils.summary_from_query', return_value='summary'):
            q = SpellbookQuery('foo')
            self.assertEqual(q.query, 'foo')
            self.assertEqual(q.patched_query, 'patched')
            self.assertEqual(q.url, 'url')
            self.assertEqual(q.summary, 'summary')
