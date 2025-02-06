import json
from django.test import TestCase
from common.abstractions import Deck
from common.inspection import json_to_python_lambda
from common.serializers import MAX_DECKLIST_LINES
from common.testing import TestCaseMixin
from .models import PROPERTY_KEYS


class WebsitePropertiesViewTests(TestCaseMixin, TestCase):
    def test_website_properties_view(self):
        response = self.client.get('/properties', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(len(result.results), len(PROPERTY_KEYS))
        result_keys = {r.key for r in result.results}
        self.assertEqual(result_keys, set(PROPERTY_KEYS))


class CardListFromTextTests(TestCase):
    def test_plain(self):
        response = self.client.post('/card-list-from-text', data='1x Sol Ring\n2x Island\n', content_type='text/plain')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content)
        self.assertEqual(result, {'main': [{'card': 'Sol Ring', 'quantity': 1}, {'card': 'Island', 'quantity': 2}], 'commanders': []})

    def test_with_command_zone(self):
        response = self.client.post('/card-list-from-text', data='1x Sol Ring\n1x Command Tower\n// Commanders\n1x Bruvac, the Grandiloquent\n', content_type='text/plain')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content)
        self.assertEqual(result, {'main': [{'card': 'Sol Ring', 'quantity': 1}, {'card': 'Command Tower', 'quantity': 1}], 'commanders': [{'card': 'Bruvac, the Grandiloquent', 'quantity': 1}]})

    def test_bad_request(self):
        data = '\n'.join(f'1x Card{i}' for i in range(MAX_DECKLIST_LINES + 1))
        response = self.client.post('/card-list-from-text', data=data, content_type='text/plain')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertIsNotNone(result.main)
        data = f'1x {"A" * 500}'
        response = self.client.post('/card-list-from-text', data=data, content_type='text/plain')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertIsNotNone(result.main)

    def test_merging_by_card_name(self):
        data = '1x Sol Ring\n1 Sol Ring\nSol Ring\n'
        response = self.client.post('/card-list-from-text', data=data, content_type='text/plain')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result: Deck = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(len(result.main), 1)
        self.assertEqual(result.main[0].card, 'Sol Ring')
        self.assertEqual(result.main[0].quantity, 3)
