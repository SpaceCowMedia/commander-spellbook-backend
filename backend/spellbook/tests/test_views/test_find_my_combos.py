import json
import itertools
import random
from django.test import Client
from spellbook.utils import launch_job_command
from spellbook.models import Card, Variant
from spellbook.variants.list_utils import merge_identities
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class FindMyCombosViewTests(AbstractModelTests):
    def setUp(self) -> None:
        super().setUp()
        launch_job_command('generate_variants', None)
        Variant.objects.update(status=Variant.Status.OK)
        self.variants = Variant.objects.filter(status=Variant.Status.OK).prefetch_related('cardinvariant_set', 'cardinvariant_set__card')
        self.variants_dict = {v.id: v for v in self.variants}
        self.variants_cards = {v.id: {c.card.name for c in v.cardinvariant_set.all()} for v in self.variants}
        self.variants_commanders = {v.id: {c.card.name for c in v.cardinvariant_set.filter(must_be_commander=True)} for v in self.variants}

    def _check_result(self,
            result,
            identity: str,
            cards: set[str],
            commanders: set[str]):
        self.assertEqual(result.results.identity, identity)
        identity_set = set(identity)
        for v in result.results.included:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.included_by_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_adding_colors:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertFalse(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_adding_colors_and_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertEqual(v.status, Variant.Status.OK)
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertFalse(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))

    def test_find_my_combos_views(self):
        c = Client()
        for content_type in ['text/plain', 'application/json']:
            with self.subTest('empty input'):
                response = c.get('/find-my-combos', follow=True, headers={'Content-Type': content_type})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertEqual(result.results.identity, 'C')
                self.assertEqual(len(result.results.included), 0)
                self.assertEqual(len(result.results.almost_included), 0)
                self.assertEqual(len(result.results.almost_included_by_adding_colors), 0)
            with self.subTest('single card'):
                card = Card.objects.get(oracle_id='00000000-0000-0000-0000-000000000001')
                if 'json' in content_type:
                    deck_list = json.dumps({'main': [card.name]})
                else:
                    deck_list = card.name
                identity = card.identity
                response = c.generic('GET', '/find-my-combos', data=deck_list, follow=True, headers={'Content-Type': content_type})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertEqual(result.results.identity, identity)
                self.assertEqual(len(result.results.included), 0)
                self.assertEqual(len(result.results.almost_included), 2)
                self.assertEqual(len(result.results.almost_included_by_adding_colors), 2)
                self.assertEqual(len(result.results.almost_included_by_changing_commanders), 0)
                self.assertEqual(len(result.results.almost_included_by_adding_colors_and_changing_commanders), 1)
                self._check_result(result, identity, {card.name}, set())
            card_names = list(Card.objects.values_list('name', flat=True))
            for card_count in [4, Card.objects.count()]:
                for commander_count in [0, 1, 2, 4]:
                    with self.subTest(f'{card_count} cards with {commander_count} commanders'):
                        for card_set in itertools.combinations(card_names, card_count):
                            for commander_set in itertools.combinations(card_set, commander_count):
                                deck_list = list(c for c in card_set if c not in commander_set)
                                commander_list = list(commander_set)
                                random.shuffle(deck_list)
                                random.shuffle(commander_list)
                                if 'json' in content_type:
                                    deck_list_str = json.dumps({'main': deck_list, 'commanders': commander_list})
                                else:
                                    deck_list_str = '\n'.join(['// Command'] + commander_list + ['// Main'] + deck_list)
                                identity = merge_identities([c.identity for c in Card.objects.filter(name__in=deck_list + commander_list)])
                                response = c.generic('GET', '/find-my-combos', data=deck_list_str, follow=True, headers={'Content-Type': content_type})
                                self.assertEqual(response.status_code, 200)
                                self.assertEqual(response.get('Content-Type'), 'application/json')
                                result = json.loads(response.content, object_hook=json_to_python_lambda)
                                self.assertEqual(result.results.identity, identity)
                                related = [v for v in self.variants if self.variants_cards[v.id].intersection(card_set)]
                                included_within_commander = [v for v in related if self.variants_cards[v.id].issubset(card_set) and self.variants_commanders[v.id].issubset(commander_set)]
                                included_outside_commander = [v for v in related if self.variants_cards[v.id].issubset(card_set) and not self.variants_commanders[v.id].issubset(commander_set)]
                                related_but_not_included = [v for v in related if not self.variants_cards[v.id].issubset(card_set)]
                                almost_included_within_identity_within_commanders = [v for v in related_but_not_included if set(v.identity).issubset(set(identity)) and self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_within_commanders_but_not_identity = [v for v in related_but_not_included if not set(v.identity).issubset(set(identity)) and self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_within_identity_but_not_commanders = [v for v in related_but_not_included if set(v.identity).issubset(set(identity)) and not self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_outside_identity_outside_commanders = [v for v in related_but_not_included if not set(v.identity).issubset(set(identity)) and not self.variants_commanders[v.id].issubset(commander_set)]
                                self.assertEqual(len(result.results.included), len(included_within_commander))
                                self.assertEqual(len(result.results.included_by_changing_commanders), len(included_outside_commander))
                                self.assertEqual(len(result.results.almost_included), len(almost_included_within_identity_within_commanders))
                                self.assertEqual(len(result.results.almost_included_by_changing_commanders), len(almost_included_within_identity_but_not_commanders))
                                self.assertEqual(len(result.results.almost_included_by_adding_colors), len(almost_included_within_commanders_but_not_identity))
                                self.assertEqual(len(result.results.almost_included_by_adding_colors_and_changing_commanders), len(almost_included_outside_identity_outside_commanders))
                                self._check_result(result, identity, set(card_set), set(commander_set))
