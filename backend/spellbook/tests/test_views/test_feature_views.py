import json
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Feature, FeatureOfCard, ZoneLocation
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
