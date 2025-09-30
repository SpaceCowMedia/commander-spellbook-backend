import logging
import random
from django.test import TestCase
from django.core.management import call_command
from common.stream import StreamToLogger


class BaseTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        random.seed(42)

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        command = 'seed_website_properties'
        logger = logging.getLogger(command)
        call_command(
            command,
            stdout=StreamToLogger(logger, logging.INFO),
            stderr=StreamToLogger(logger, logging.ERROR)
        )

    def setUp(self):
        super().setUp()
        random.seed(42)
        logging.disable(logging.INFO)
