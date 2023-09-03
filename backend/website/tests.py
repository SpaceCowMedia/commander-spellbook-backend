import json
import logging
import random
from django.test import Client, TestCase
from django.core.management import call_command
from common.stream import StreamToLogger
from common.inspection import json_to_python_lambda
from .models import PROPERTY_KEYS


class WebsitePropertiesViewTests(TestCase):
    def setUp(self):
        logging.disable(logging.INFO)
        random.seed(42)
        command = 'seed_website_properties'
        logger = logging.getLogger(command)
        call_command(
            command,
            stdout=StreamToLogger(logger, logging.INFO),
            stderr=StreamToLogger(logger, logging.ERROR)
        )

    def test_website_properties_view(self):
        c = Client()
        response = c.get('/properties', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(len(result.results), len(PROPERTY_KEYS))
        result_keys = {r.key for r in result.results}
        self.assertEqual(result_keys, set(PROPERTY_KEYS))
