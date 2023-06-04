import json
import logging
from django.test import Client
from django.core.management import call_command
from spellbook.utils import StreamToLogger
from website.models import PROPERTY_KEYS
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class WebsitePropertiesViewTests(AbstractModelTests):
    def setUp(self):
        super().setUp()
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
