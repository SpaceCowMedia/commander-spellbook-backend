import json
from itertools import chain, combinations
from typing import Iterable
from django.urls import reverse
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Template, Variant, CardInVariant, Feature
from ..testing import SpellbookTestCaseWithSeeding


def powerset(iterable):
    "Subsequences of the iterable from shortest to longest."
    # powerset([1,2,3]) → () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s) + 1))


class EstimateBracketViewTests(SpellbookTestCaseWithSeeding):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.generate_and_publish_variants()
        CardInVariant.objects.filter(card_id=cls.c1_id, variant__card_count=2).update(quantity=2)
        Feature.objects.filter(pk=cls.f4_id).update(name='Infinite Extra Turns')
        cls.update_variants()
        cls.bulk_serialize_variants()

    def _check_result(
            self,
            result,
            cards: Iterable[str],
            commanders: Iterable[str],
    ):
        self.assertIn(result.bracket_tag, Variant.BracketTag.values)
        cards_in_db = (Card.objects.get(name=name) for collection in (cards, commanders) for name in collection)
        if any(not c.legal_commander for c in cards_in_db):
            self.assertEqual(result.bracket_tag, Variant.BracketTag.BANNED)
        elif any(c.game_changer or c.extra_turn or c.mass_land_denial for c in cards_in_db):
            self.assertNotIn(result.bracket_tag, [Variant.BracketTag.EXHIBITION, Variant.BracketTag.CORE])
        for classified_combo in result.combos:
            combo = classified_combo.combo
            for card in combo.uses:
                name = card.card.name
                self.assertIn(name, cards or commanders)

    def test_estimate_bracket_views(self):
        for content_type in ['text/plain', 'application/json']:
            with self.subTest('empty input'):
                response = self.client.post(reverse('estimate-bracket'), follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self._check_result(result, set(), set())
                self.assertEqual(result.bracket_tag, Variant.BracketTag.EXHIBITION)
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
            cards: list[str] = sorted(Card.objects.values_list('name', flat=True))
            legal_cards: list[str] = sorted(Card.objects.filter(legal_commander=True).values_list('name', flat=True))
            with self.subTest('all cards'):
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in cards]})
                else:
                    data = '\n'.join(f'2 {card}' for card in cards)
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertEqual(result.bracket_tag, Variant.BracketTag.BANNED)
                self.assertTrue(any(c.banned for c in result.cards))
                self._check_result(result, cards, set())
            for card_set in powerset(legal_cards):
                with self.subTest('legal cards', cards=card_set):
                    if 'json' in content_type:
                        data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in card_set]})
                    else:
                        data = '\n'.join(f'2 {card}' for card in card_set)
                    response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self.assertFalse(any(c.banned for c in result.cards))
                    self._check_result(result, card_set, set())
            with self.subTest('template as extra turns'):
                t = Template.objects.get(pk=self.t2_id)
                t.name = 'Extra Turn Template'
                t.save()
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in legal_cards]})
                else:
                    data = '\n'.join(f'2 {card}' for card in legal_cards)
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertEqual(result.bracket_tag, Variant.BracketTag.RUTHLESS)
                self.assertGreaterEqual(sum(t.quantity for t in result.templates if t.extra_turn), 1)
                self._check_result(result, legal_cards, set())
