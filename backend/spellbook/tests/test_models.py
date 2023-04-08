from django.test import TestCase
from .populate_db import populate_db
from spellbook.models import Card



class AbstractModelTests(TestCase):
    def setUp(self) -> None:
        populate_db()


class CardTests(AbstractModelTests):
    def test_card(self):
        c = Card.objects.get(name='A')
        self.assertTrue(c.legal)
        self.assertFalse(c.spoiler)

    def test_card_query_string(self):
        c = Card.objects.get(name='A')
        self.assertEqual(c.query_string(), 'q=%21%22A%22')
