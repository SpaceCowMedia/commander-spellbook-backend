import logging
import random
from django.test import TestCase
from django.core.management import call_command
from common.stream import StreamToLogger


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        command = 'seed_website_properties'
        logger = logging.getLogger(command)
        call_command(
            command,
            stdout=StreamToLogger(logger, logging.INFO),
            stderr=StreamToLogger(logger, logging.ERROR)
        )

    def setUp(self):
        logging.disable(logging.INFO)
        random.seed(42)
