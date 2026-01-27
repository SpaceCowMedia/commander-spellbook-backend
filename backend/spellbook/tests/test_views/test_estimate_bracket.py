import json
from itertools import chain
from typing import Iterable
from django.urls import reverse
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Template, Variant, CardInVariant, Feature
from ..testing import SpellbookTestCaseWithSeeding


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
        if any(c.game_changer or c.extra_turn or c.mass_land_denial for c in cards_in_db):
            self.assertNotIn(result.bracket_tag, [Variant.BracketTag.EXHIBITION, Variant.BracketTag.CORE])
        for combo in chain(
            result.mass_land_denial_combos,
            result.extra_turns_combos,
            result.lock_combos,
            result.skip_turns_combos,
            result.control_all_opponents_combos,
            result.control_some_opponents_combos,
            result.skip_turns_combos,
            (c.combo for c in result.two_card_combos),
        ):
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
            cards = sorted(Card.objects.values_list('name', flat=True))
            with self.subTest('all cards'):
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in cards]})
                else:
                    data = '\n'.join(f'2 {card}' for card in cards)
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertGreater(result.bracket_tag, Variant.BracketTag.EXHIBITION)
                self._check_result(result, cards, set())
            with self.subTest('template as extra turns'):
                t = Template.objects.get(pk=self.t2_id)
                t.name = 'Extra Turn Template'
                t.save()
                if 'json' in content_type:
                    data = json.dumps({'main': [{'card': card, 'quantity': 2} for card in cards]})
                else:
                    data = '\n'.join(f'2 {card}' for card in cards)
                response = self.client.post(reverse('estimate-bracket'), data, follow=True, content_type=content_type)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertGreaterEqual(result.bracket_tag, Variant.BracketTag.POWERFUL)
                self.assertGreaterEqual(len(result.extra_turn_templates), 1)
                self._check_result(result, cards, set())
