import json
from django.test import TestCase
from spellbook.models import Card, Template
from ..testing import TestCaseMixinWithSeeding
from common.inspection import json_to_python_lambda


class CardViewsTests(TestCaseMixinWithSeeding, TestCase):
    def card_assertions(self, card_result):
        c = Card.objects.get(id=card_result.id)
        self.assertEqual(card_result.id, c.id)
        self.assertEqual(card_result.name, c.name)
        self.assertEqual(card_result.oracle_id, str(c.oracle_id))
        self.assertEqual(card_result.type_line, c.type_line)
        self.assertEqual(card_result.oracle_text, c.oracle_text)
        self.assertEqual(card_result.identity, c.identity)
        self.assertEqual(card_result.spoiler, c.spoiler)
        self.assertEqual(card_result.keywords, c.keywords)
        self.assertEqual(card_result.mana_value, c.mana_value)
        self.assertEqual(card_result.reserved, c.reserved)
        self.assertEqual(card_result.variant_count, c.variant_count)
        self.assertEqual(card_result.legalities.commander, c.legal_commander)
        self.assertEqual(card_result.legalities.pauper_commander_main, c.legal_pauper_commander_main)
        self.assertEqual(card_result.legalities.pauper_commander, c.legal_pauper_commander)
        self.assertEqual(card_result.legalities.oathbreaker, c.legal_oathbreaker)
        self.assertEqual(card_result.legalities.predh, c.legal_predh)
        self.assertEqual(card_result.legalities.brawl, c.legal_brawl)
        self.assertEqual(card_result.legalities.vintage, c.legal_vintage)
        self.assertEqual(card_result.legalities.legacy, c.legal_legacy)
        self.assertEqual(card_result.legalities.premodern, c.legal_premodern)
        self.assertEqual(card_result.legalities.modern, c.legal_modern)
        self.assertEqual(card_result.legalities.pioneer, c.legal_pioneer)
        self.assertEqual(card_result.legalities.standard, c.legal_standard)
        self.assertEqual(card_result.legalities.pauper, c.legal_pauper)
        self.assertEqual(card_result.prices.tcgplayer, str(c.price_tcgplayer))
        self.assertEqual(card_result.prices.cardkingdom, str(c.price_cardkingdom))
        self.assertEqual(card_result.prices.cardmarket, str(c.price_cardmarket))
        self.assertEqual(len(card_result.features), c.features.count())
        card_features_dict = {f.id: f for f in c.featureofcard_set.all()}  # type: ignore
        for feature_of_card in card_result.features:
            self.assertIn(feature_of_card.id, card_features_dict)
            feature_through = card_features_dict[feature_of_card.id]
            self.assertEqual(feature_of_card.battlefield_card_state, feature_through.battlefield_card_state)
            self.assertEqual(feature_of_card.exile_card_state, feature_through.exile_card_state)
            self.assertEqual(feature_of_card.library_card_state, feature_through.library_card_state)
            self.assertEqual(feature_of_card.graveyard_card_state, feature_through.graveyard_card_state)
            self.assertEqual(feature_of_card.must_be_commander, feature_through.must_be_commander)
            self.assertEqual(feature_of_card.zone_locations, list(feature_through.zone_locations))
            self.assertEqual(feature_of_card.quantity, feature_through.quantity)

    def test_cards_list_view(self):
        response = self.client.get('/cards', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        card_count = Card.objects.count()
        self.assertEqual(len(result.results), card_count)
        for i in range(card_count):
            self.card_assertions(result.results[i])

    def test_cards_detail_view(self):
        response = self.client.get('/cards/{}'.format(self.c1_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.c1_id)
        self.card_assertions(result)

    def test_cards_list_view_ordering(self):
        self.generate_and_publish_variants()
        for ordering, assertion in [
            ('variant_count', lambda a, b: self.assertGreaterEqual(a.variant_count, b.variant_count)),
            ('-variant_count', lambda a, b: self.assertLessEqual(a.variant_count, b.variant_count)),
            ('name', lambda a, b: self.assertGreaterEqual(a.name, b.name)),
            ('-name', lambda a, b: self.assertLessEqual(a.name, b.name)),
        ]:
            response = self.client.get(f'/cards?ordering={ordering}', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            card_count = Card.objects.count()
            self.assertEqual(len(result.results), card_count)
            previous_variant = None
            variant_count_values = set[int()]()
            for i in range(card_count):
                self.card_assertions(result.results[i])
                if i > 0:
                    assertion(result.results[i], previous_variant)
                previous_variant = result.results[i]
                variant_count_values.add(result.results[i].variant_count)  # type: ignore
            self.assertGreater(len(variant_count_values), 1)

    def test_cards_list_view_replacement_filter(self):
        for template_id in [self.t1_id, self.t2_id]:
            response = self.client.get(f'/cards?replaces={template_id}', follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            card_ids = {c.id for c in result.results}
            replacements = set(Template.objects.get(id=template_id).replacements.values_list('id', flat=True))
            self.assertSetEqual(card_ids, replacements)
