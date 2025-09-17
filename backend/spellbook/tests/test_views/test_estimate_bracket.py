import json
import random
from typing import Iterable
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Variant, CardInVariant
from ..testing import TestCaseMixinWithSeeding


class EstimateBracketViewTests(TestCaseMixinWithSeeding, TestCase):
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
            cards: Iterable[str],
            commanders: Iterable[str],
    ):
        self.assertIn(result.bracket_tag, Variant.BracketTag.values)
        cards_in_db = (Card.objects.get(name=name) for collection in (cards, commanders) for name in collection)
        if any(c.game_changer or c.extra_turn or c.mass_land_denial for c in cards_in_db):
            self.assertNotIn(result.bracket_tag, [Variant.BracketTag.CASUAL, Variant.BracketTag.PRECON_APPROPRIATE])

    def test_estimate_bracket_views(self):
        for content_type in ['text/plain', 'application/json']:
            with self.subTest('empty input'):
                response = self.client.post(reverse('estimate-bracket'), follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self._check_result(result, set(), set())
                self.assertEqual(result.bracket_tag, Variant.BracketTag.CASUAL)
            with self.subTest('one card'):
                card = Card.objects.get(id=self.c1_id)
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card.name}]})
                else:
                    data = card.name
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self._check_result(result, set([card.name]), set())
            with self.subTest('all cards'):
                cards = sorted(Card.objects.values_list('name', flat=True))
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in cards]})
                else:
                    data = '\n'.join(f'2 {card}' for card in cards)
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertGreater(result.bracket_tag, Variant.BracketTag.CASUAL)
                self._check_result(result, cards, set())
