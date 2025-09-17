import json
from django.test import TestCase
from rest_framework import status


class RestApiTestCase(TestCase):
    def test_root_endpoint(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content)
        self.assertIsInstance(result, dict)
        for key, value in result.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)
            self.assertRegex(value, r'^https?://')
