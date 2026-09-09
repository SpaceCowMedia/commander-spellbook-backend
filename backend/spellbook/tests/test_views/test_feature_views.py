import json
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Feature, FeatureOfCard, ZoneLocation
from ..testing import SpellbookTestCaseWithSeeding
from django.urls import reverse


class FeatureViewsTests(SpellbookTestCaseWithSeeding):
    def feature_assertions(self, feature_result):
        f = Feature.objects.get(id=feature_result.id)
        self.assertEqual(feature_result.id, f.id)
        self.assertEqual(feature_result.name, f.name)
        self.assertEqual(feature_result.uncountable, f.uncountable)
        self.assertEqual(feature_result.status, f.status)

    def test_features_list_view(self):
        response = self.client.get(reverse('features-list'), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        feature_count = Feature.objects.exclude(status=Feature.Status.HIDDEN_UTILITY).count()
        self.assertEqual(len(result.results), feature_count)
        for i in range(feature_count):
            self.feature_assertions(result.results[i])

    def test_features_detail_view(self):
        response = self.client.get(reverse('features-detail', args=[self.f2_id]), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.f2_id)
        self.feature_assertions(result)

    def test_features_cards_filter(self):
        FeatureOfCard.objects.create(card_id=self.c1_id, feature_id=self.f2_id, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1)
        FeatureOfCard.objects.create(card_id=self.c1_id, feature_id=self.f2_id, zone_locations=ZoneLocation.BATTLEFIELD, quantity=2)
        response = self.client.get(reverse('features-list') + '?cards=' + str(self.c1_id), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(len(result.results), 1)
        self.assertEqual(result.results[0].id, self.f2_id)
        self.feature_assertions(result.results[0])

    def test_features_cards_filter_names_the_card_by_its_number(self):
        '''The filter takes the id the API publishes for a card, which is its number, not its key.'''
        card = Card.objects.create(name='Numbered Card', number=900, type_line='Creature', legal_commander=True)
        self.assertNotEqual(card.pk, card.number)
        self.assertFalse(Card.objects.filter(number=card.pk).exists())
        FeatureOfCard.objects.create(card_id=card.number, feature_id=self.f2_id, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1)
        response = self.client.get(reverse('features-list') + '?cards=' + str(card.number), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual([f.id for f in result.results], [self.f2_id])
        response = self.client.get(reverse('features-list') + '?cards=' + str(card.pk), follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_features_cards_filter_takes_more_than_one_card(self):
        '''The parameter can be repeated, the way the generated filter it replaced accepted it.'''
        first = Card.objects.create(name='First Numbered Card', number=900, type_line='Creature', legal_commander=True)
        second = Card.objects.create(name='Second Numbered Card', number=901, type_line='Creature', legal_commander=True)
        FeatureOfCard.objects.create(card_id=first.number, feature_id=self.f2_id, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1)
        FeatureOfCard.objects.create(card_id=second.number, feature_id=self.f3_id, zone_locations=ZoneLocation.BATTLEFIELD, quantity=1)
        response = self.client.get(reverse('features-list'), query_params={'cards': [first.number, second.number]}, follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertSetEqual({f.id for f in result.results}, {self.f2_id, self.f3_id})
