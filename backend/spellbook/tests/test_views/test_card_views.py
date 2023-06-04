import json
from django.test import Client
from spellbook.models import Card
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class CardViewsTests(AbstractModelTests):
    def card_assertions(self, card_result):
        c = Card.objects.get(id=card_result.id)
        self.assertEqual(card_result.id, c.id)
        self.assertEqual(card_result.name, c.name)
        self.assertEqual(card_result.oracle_id, str(c.oracle_id))
        self.assertEqual(card_result.identity, c.identity)
        self.assertEqual(card_result.legal, c.legal)
        self.assertEqual(card_result.spoiler, c.spoiler)
        self.assertEqual(len(card_result.features), c.features.count())
        feature_list = [f.id for f in c.features.all()]
        for f in card_result.features:
            self.assertIn(f.id, feature_list)

    def test_cards_list_view(self):
        c = Client()
        response = c.get('/cards', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        cards_count = Card.objects.count()
        self.assertEqual(len(result.results), cards_count)
        for i in range(cards_count):
            self.card_assertions(result.results[i])

    def test_cards_detail_view(self):
        c = Client()
        response = c.get('/cards/{}'.format(self.c1_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.c1_id)
        self.card_assertions(result)
