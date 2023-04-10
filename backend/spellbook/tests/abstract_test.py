from django.test import TestCase
from django.conf import settings
from .populate_db import populate_db


class AbstractModelTests(TestCase):
    def setUp(self) -> None:
        populate_db()
        settings.ASYNC_GENERATION = False
