import json
from rest_framework import status
from website.models import PROPERTY_KEYS
from common.inspection import json_to_python_lambda
from .testing import BaseTestCase


class WebsitePropertiesViewTests(BaseTestCase):
    def test_website_properties_view(self):
        response = self.client.get('/properties', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(len(result.results), len(PROPERTY_KEYS))
        result_keys = {r.key for r in result.results}
        self.assertEqual(result_keys, set(PROPERTY_KEYS))
