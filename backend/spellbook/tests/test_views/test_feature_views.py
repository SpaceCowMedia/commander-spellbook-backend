import json
from django.test import TestCase
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Feature
from ..testing import TestCaseMixinWithSeeding


class FeatureViewsTests(TestCaseMixinWithSeeding, TestCase):
    def feature_assertions(self, feature_result):
        f = Feature.objects.get(id=feature_result.id)
        self.assertEqual(feature_result.id, f.id)
        self.assertEqual(feature_result.name, f.name)
        self.assertEqual(feature_result.uncountable, f.uncountable)

    def test_features_list_view(self):
        response = self.client.get('/features', follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        feature_count = Feature.objects.exclude(status=Feature.Status.UTILITY).count()
        self.assertEqual(len(result.results), feature_count)
        for i in range(feature_count):
            self.feature_assertions(result.results[i])

    def test_features_detail_view(self):
        response = self.client.get('/features/{}'.format(self.f2_id), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.f2_id)
        self.feature_assertions(result)
