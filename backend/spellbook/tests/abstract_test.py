import logging
from django.test import TestCase
from django.conf import settings
from .populate_db import populate_db


class AbstractModelTests(TestCase):
    def setUp(self) -> None:
        settings.ASYNC_GENERATION = False
        logging.disable(logging.INFO)
        populate_db(self)
