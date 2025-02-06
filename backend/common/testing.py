import logging
import random
from multiset import BaseMultiset
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

    def assertMultisetEqual(self, a, b):
        if isinstance(a, BaseMultiset):
            a = {k: v for k, v in a.items()}
        if isinstance(b, BaseMultiset):
            b = {k: v for k, v in b.items()}
        self.assertDictEqual(a, b)
