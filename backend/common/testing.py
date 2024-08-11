import logging
import random
from multiset import BaseMultiset
from django.test import SimpleTestCase


class TestCaseMixin(SimpleTestCase):
    def setUp(self) -> None:
        logging.disable(logging.INFO)
        random.seed(42)

    def assertMultisetEqual(self, a, b):
        if isinstance(a, BaseMultiset):
            a = {k: v for k, v in a.items()}
        if isinstance(b, BaseMultiset):
            b = {k: v for k, v in b.items()}
        self.assertDictEqual(a, b)
