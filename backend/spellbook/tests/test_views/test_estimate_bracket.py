import json
import random
from django.test import TestCase
from multiset import FrozenMultiset
from spellbook.models import Card, Variant, CardInVariant
from ..testing import TestCaseMixinWithSeeding
from common.inspection import json_to_python_lambda


class FindMyCombosViewTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.generate_and_publish_variants()
        Variant.objects.filter(id__in=random.sample(list(Variant.objects.values_list('id', flat=True)), 3)).update(status=Variant.Status.EXAMPLE)
        CardInVariant.objects.filter(card_id=self.c1_id, variant__card_count=2).update(quantity=2)
        self.update_variants()
        self.bulk_serialize_variants()

    def _check_result(
            self,
            result,
            cards: FrozenMultiset[str],
            commanders: FrozenMultiset[str],
            single: bool,
    ):
        self.assertGreaterEqual(result.bracket, 1)
        self.assertLessEqual(result.bracket, 5)
        self.assertIsInstance(result.explanation, str)
        self.assertGreaterEqual(len(result.explanation), 1)
        cards_in_db = [Card.objects.get(name=name) for name in cards | commanders]
        if any(c.game_changer or c.extra_turn or c.mass_land_destruction for c in cards_in_db):
            self.assertGreaterEqual(result.bracket, 3)
        if single:
            self.assertNotIn('decklist', result.explanation)
        else:
            self.assertIn('decklist', result.explanation)

    def test_estimate_bracket_views(self):
        for content_type in ['text/plain', 'application/json']:
            for single in [True, False]:
                with self.subTest('empty input'):
                    response = self.client.post('/api/estimate-bracket/', follow=True, content_type=content_type, query_params={'single': single})  # type: ignore
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self._check_result(result, FrozenMultiset(), FrozenMultiset(), single)
                    self.assertEqual(result.bracket, 2)
                with self.subTest('one card'):
                    card = Card.objects.get(id=self.c1_id)
                    if 'json' in content_type:
                        data = json.dumps({'main': [{'card': card.name}]})
                    else:
                        data = card.name
                    response = self.client.post('/api/estimate-bracket/', data, follow=True, content_type=content_type, query_params={'single': single})  # type: ignore
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self._check_result(result, FrozenMultiset([card.name]), FrozenMultiset(), single)
                with self.subTest('all cards'):
                    cards = FrozenMultiset(Card.objects.values_list('name', flat=True))
                    if 'json' in content_type:
                        data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in cards]})
                    else:
                        data = '\n'.join(f'2 {card}' for card in cards)
                    response = self.client.post('/api/estimate-bracket/', data, follow=True, content_type=content_type, query_params={'single': single})  # type: ignore
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self.assertGreater(result.bracket, 2)
                    self._check_result(result, cards, FrozenMultiset(), single)
