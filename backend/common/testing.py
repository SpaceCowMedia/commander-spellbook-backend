import logging
import random
from django.test import SimpleTestCase
from django.core.management import call_command
from common.stream import StreamToLogger


class TestCaseMixin(SimpleTestCase):
    def setUp(self) -> None:
        logging.disable(logging.INFO)
        random.seed(42)
        command = 'seed_website_properties'
        logger = logging.getLogger(command)
        call_command(
            command,
            stdout=StreamToLogger(logger, logging.INFO),
            stderr=StreamToLogger(logger, logging.ERROR)
        )
