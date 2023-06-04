import json
import itertools
import random
from django.test import Client
from spellbook.utils import launch_job_command
from spellbook.models import Card, Variant, IngredientInCombination
from spellbook.variants.list_utils import merge_identities
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class FindMyCombosViewTests(AbstractModelTests):
    def setUp(self) -> None:
        super().setUp()
        launch_job_command('generate_variants', None)
        Variant.objects.update(status=Variant.Status.OK)

    def test_find_my_combos_views(self):
        c = Client()
        for content_type in ['text/plain', 'application/json']:
            with self.subTest('empty input'):
                response = c.get('/find-my-combos', follow=True, headers={'Content-Type': content_type})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertEqual(result.identity, 'C')
                self.assertEqual(len(result.included), 0)
                self.assertEqual(len(result.almost_included), 0)
                self.assertEqual(len(result.almost_included_by_adding_colors), 0)
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
                self.assertEqual(result.identity, identity)
                self.assertEqual(len(result.included), 0)
                self.assertEqual(len(result.almost_included), 2)
                self.assertEqual(len(result.almost_included_by_adding_colors), 2)
                for v in result.almost_included:
                    self.assertTrue(set(v.identity).issubset(set(identity)))
                    v = Variant.objects.get(id=v.id)
                    self.assertEqual(v.status, Variant.Status.OK)
                    self.assertIn(card.name, set(v.uses.values_list('name', flat=True)))
                for v in result.almost_included_by_adding_colors:
                    self.assertTrue(set(v.identity).issuperset(set(identity)))
                    v = Variant.objects.get(id=v.id)
                    self.assertEqual(v.status, Variant.Status.OK)
                    self.assertIn(card.name, set(v.uses.values_list('name', flat=True)))
            variants = Variant.objects.filter(status=Variant.Status.OK).prefetch_related('cardinvariant_set', 'cardinvariant_set__card')
            variants_cards = {v.id: {c.card.name for c in v.cardinvariant_set.all()} for v in variants}
            variants_commanders = {v.id: {c.card.name for c in v.cardinvariant_set.filter(zone_locations=IngredientInCombination.ZoneLocation.COMMAND_ZONE)} for v in variants}
            card_names = Card.objects.values_list('name', flat=True)
            for card_count in [4, Card.objects.count()]:
                for commander_count in [0, 1, 2, 4]:
                    with self.subTest(f'{card_count} cards with {commander_count} commanders'):
                        for card_set in itertools.combinations(card_names, card_count):
                            for commander_set in itertools.combinations(card_set, commander_count):
                                card_set: set[str] = set(card_set)
                                commander_set: set[str] = set(commander_set)
                                deck_list = list(card_set - commander_set)
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
                                self.assertEqual(result.identity, identity)
                                included = [v for v in variants if variants_cards[v.id].issubset(card_set) and variants_commanders[v.id].issubset(commander_set)]
                                almost_included = [v for v in variants if variants_cards[v.id].intersection(card_set) and not variants_cards[v.id].issubset(card_set) and variants_commanders[v.id].issubset(commander_set)]
                                almost_included_within_identity = [v for v in almost_included if set(v.identity).issubset(set(identity))]
                                self.assertEqual(len(result.included), len(included))
                                self.assertEqual(len(result.almost_included), len(almost_included_within_identity))
                                self.assertEqual(len(result.almost_included_by_adding_colors), len(almost_included) - len(almost_included_within_identity))
                                for v in result.included:
                                    self.assertTrue(set(v.identity).issubset(set(identity)))
                                    v = Variant.objects.get(id=v.id)
                                    self.assertEqual(v.status, Variant.Status.OK)
                                    self.assertTrue(set(v.uses.values_list('name', flat=True)).issubset(card_set))
                                for v in result.almost_included:
                                    self.assertTrue(set(v.identity).issubset(set(identity)))
                                    v = Variant.objects.get(id=v.id)
                                    self.assertEqual(v.status, Variant.Status.OK)
                                    self.assertTrue(set(v.uses.values_list('name', flat=True)).intersection(card_set))
                                for v in result.almost_included_by_adding_colors:
                                    self.assertFalse(set(v.identity).issubset(set(identity)))
                                    v = Variant.objects.get(id=v.id)
                                    self.assertEqual(v.status, Variant.Status.OK)
                                    self.assertTrue(set(v.uses.values_list('name', flat=True)).intersection(card_set))
