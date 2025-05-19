import json
import itertools
import random
from django.test import TestCase
from rest_framework import status
from common.inspection import json_to_python_lambda
from multiset import FrozenMultiset
from spellbook.models import Card, Template, Variant, merge_identities, CardInVariant
from ..testing import TestCaseMixinWithSeeding


class FindMyCombosViewTests(TestCaseMixinWithSeeding, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.generate_and_publish_variants()
        Variant.objects.filter(id__in=random.sample(list(Variant.objects.values_list('id', flat=True)), 3)).update(status=Variant.Status.EXAMPLE)
        CardInVariant.objects.filter(card_id=self.c1_id, variant__card_count=2).update(quantity=2)
        self.bulk_serialize_variants()
        self.variants = Variant.objects.filter(status__in=Variant.public_statuses()).prefetch_related('cardinvariant_set', 'cardinvariant_set__card')
        self.variants_dict = {v.id: v for v in self.variants}
        self.variants_cards = {v.id: FrozenMultiset({c.card.name: c.quantity for c in v.cardinvariant_set.all()}) for v in self.variants}
        self.variants_templates = {v.id: FrozenMultiset({t.template.name: t.quantity for t in v.templateinvariant_set.all()}) for v in self.variants}
        self.variants_commanders = {v.id: FrozenMultiset({c.card.name: c.quantity for c in v.cardinvariant_set.filter(must_be_commander=True)}) for v in self.variants}

    def _check_result(
            self,
            result,
            identity: str,
            cards: FrozenMultiset[str],
            commanders: FrozenMultiset[str],
    ):
        self.assertEqual(result.results.identity, identity)
        identity_set = set(identity) | {'C'}
        for v in result.results.included:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.included_by_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_adding_colors:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertFalse(set(v.identity).issubset(identity_set))
            self.assertTrue(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertTrue(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))
        for v in result.results.almost_included_by_adding_colors_and_changing_commanders:
            v = self.variants_dict[v.id]
            self.assertIn(v.status, Variant.public_statuses())
            self.assertTrue(bool(self.variants_cards[v.id].intersection(cards)))
            self.assertFalse(self.variants_cards[v.id].issubset(cards))
            self.assertFalse(set(v.identity).issubset(identity_set))
            self.assertFalse(self.variants_commanders[v.id].issubset(commanders))

    def test_find_my_combos_views(self):
        for content_type in ['text/plain', 'application/json']:
            for using_ids in [False, True]:
                with self.subTest('empty input'):
                    response = self.client.get('/find-my-combos', follow=True, headers={'Content-Type': content_type})  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self.assertEqual(result.results.identity, 'C')
                    self.assertEqual(len(result.results.included), 0)
                    self.assertEqual(len(result.results.almost_included), 0)
                    self.assertEqual(len(result.results.almost_included_by_adding_colors), 0)
                    self.assertEqual(len(result.results.almost_included_by_changing_commanders), 0)
                    self.assertEqual(len(result.results.almost_included_by_adding_colors_and_changing_commanders), 0)
                with self.subTest('single card'):
                    card = Card.objects.get(id=self.c1_id)
                    card_str = str(card.id) if using_ids else card.name
                    if 'json' in content_type:
                        deck_list = json.dumps({'main': [{'card': card_str, 'quantity': 2}]})
                    else:
                        deck_list = f'2 {card_str}'
                    identity = card.identity
                    response = self.client.generic('GET', '/find-my-combos', data=deck_list, follow=True, headers={'Content-Type': content_type})  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)  # type: ignore
                    self.assertEqual(response.get('Content-Type'), 'application/json')  # type: ignore
                    result = json.loads(response.content, object_hook=json_to_python_lambda)  # type: ignore
                    self.assertEqual(result.results.identity, identity)
                    self.assertEqual(len(result.results.included), 0)
                    self.assertEqual(len(result.results.almost_included), 2)
                    self.assertEqual(len(result.results.almost_included_by_adding_colors), 0)
                    self.assertEqual(len(result.results.almost_included_by_changing_commanders), 0)
                    self.assertEqual(len(result.results.almost_included_by_adding_colors_and_changing_commanders), 0)
                    self._check_result(result, identity, FrozenMultiset({card.name}), FrozenMultiset())
            card_names = list(Card.objects.values_list('name', flat=True))
            for card_count in [4, Card.objects.count()]:
                for commander_count in [0, 1, 2, 4]:
                    with self.subTest(f'{card_count} cards with {commander_count} commanders'):
                        for card_set in itertools.combinations(card_names, card_count):
                            card_set = FrozenMultiset[str]({c: q for q, c in enumerate(card_set, start=1)})
                            template_set = FrozenMultiset[str]({t.name: sum(card_set.get(c.name, 0) for c in t.replacements.all()) if not t.scryfall_query else 1 for t in Template.objects.all()})
                            for commander_set in itertools.combinations(card_set.items(), commander_count):
                                commander_set = FrozenMultiset[str](dict(commander_set))
                                commander_list = list(commander_set.items())
                                deck_list = list((card_set - commander_set).items())
                                random.shuffle(deck_list)
                                random.shuffle(commander_list)
                                if 'json' in content_type:
                                    deck_list_str = json.dumps({'main': [{'card': c, 'quantity': q} for c, q in deck_list], 'commanders': [{'card': c, 'quantity': q} for c, q in commander_list]})
                                else:
                                    deck_list_str = '\n'.join(['// Command'] + [f'{q}x {c} [ALFA]' for c, q in commander_list] + ['// Main'] + [f'{q} {c} (XD)' for c, q in deck_list])
                                identity = merge_identities(c.identity for c in Card.objects.filter(name__in=[c for c, _ in deck_list + commander_list]))
                                identity_set = set(identity) | {'C'}
                                response = self.client.generic('GET', '/find-my-combos', data=deck_list_str, follow=True, headers={'Content-Type': content_type})  # type: ignore
                                self.assertEqual(response.status_code, status.HTTP_200_OK)  # type: ignore
                                self.assertEqual(response.get('Content-Type'), 'application/json')  # type: ignore
                                result = json.loads(response.content, object_hook=json_to_python_lambda)  # type: ignore
                                self.assertEqual(result.results.identity, identity)
                                related = [v for v in self.variants if len(self.variants_cards[v.id].difference(card_set)) + len(self.variants_templates[v.id].difference(template_set)) <= 1]
                                included_within_commander = [v for v in related if self.variants_cards[v.id].issubset(card_set) and self.variants_templates[v.id].issubset(template_set) and self.variants_commanders[v.id].issubset(commander_set)]
                                included_outside_commander = [v for v in related if self.variants_cards[v.id].issubset(card_set) and self.variants_templates[v.id].issubset(template_set) and not self.variants_commanders[v.id].issubset(commander_set)]
                                related_but_not_included = [v for v in related if not (self.variants_cards[v.id].issubset(card_set) and self.variants_templates[v.id].issubset(template_set))]
                                almost_included_within_identity_within_commanders = [v for v in related_but_not_included if set(v.identity).issubset(identity_set) and self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_within_commanders_but_not_identity = [v for v in related_but_not_included if not set(v.identity).issubset(identity_set) and self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_within_identity_but_not_commanders = [v for v in related_but_not_included if set(v.identity).issubset(identity_set) and not self.variants_commanders[v.id].issubset(commander_set)]
                                almost_included_outside_identity_outside_commanders = [v for v in related_but_not_included if not set(v.identity).issubset(identity_set) and not self.variants_commanders[v.id].issubset(commander_set)]
                                self.assertEqual(len(result.results.included), len(included_within_commander))
                                self.assertEqual(len(result.results.included_by_changing_commanders), len(included_outside_commander))
                                self.assertEqual(len(result.results.almost_included), len(almost_included_within_identity_within_commanders))
                                self.assertEqual(len(result.results.almost_included_by_changing_commanders), len(almost_included_within_identity_but_not_commanders))
                                self.assertEqual(len(result.results.almost_included_by_adding_colors), len(almost_included_within_commanders_but_not_identity))
                                self.assertEqual(len(result.results.almost_included_by_adding_colors_and_changing_commanders), len(almost_included_outside_identity_outside_commanders))
                                self._check_result(result, identity, card_set, commander_set)
