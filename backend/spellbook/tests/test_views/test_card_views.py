import json
from django.test import Client
from spellbook.models import Card
from ..abstract_test import AbstractModelTests
from common.inspection import json_to_python_lambda


class CardViewsTests(AbstractModelTests):
    def card_assertions(self, card_result):
        c = Card.objects.get(id=card_result.id)
        self.assertEqual(card_result.id, c.id)
        self.assertEqual(card_result.name, c.name)
        self.assertEqual(card_result.oracle_id, str(c.oracle_id))
        self.assertEqual(card_result.type_line, c.type_line)
        self.assertEqual(card_result.oracle_text, c.oracle_text)
        self.assertEqual(card_result.identity, c.identity)
        self.assertEqual(card_result.legalities.commander, c.legal_commander)
        self.assertEqual(card_result.legalities.pauper_commander_main, c.legal_pauper_commander_main)
        self.assertEqual(card_result.legalities.pauper_commander, c.legal_pauper_commander)
        self.assertEqual(card_result.legalities.oathbreaker, c.legal_oathbreaker)
        self.assertEqual(card_result.legalities.predh, c.legal_predh)
        self.assertEqual(card_result.legalities.brawl, c.legal_brawl)
        self.assertEqual(card_result.legalities.vintage, c.legal_vintage)
        self.assertEqual(card_result.legalities.legacy, c.legal_legacy)
        self.assertEqual(card_result.legalities.modern, c.legal_modern)
        self.assertEqual(card_result.legalities.pioneer, c.legal_pioneer)
        self.assertEqual(card_result.legalities.standard, c.legal_standard)
        self.assertEqual(card_result.legalities.pauper, c.legal_pauper)
        self.assertEqual(card_result.prices.tcgplayer, str(c.price_tcgplayer))
        self.assertEqual(card_result.prices.cardkingdom, str(c.price_cardkingdom))
        self.assertEqual(card_result.prices.cardmarket, str(c.price_cardmarket))
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
