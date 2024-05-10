import json
from django.test import Client
from spellbook.models import Feature
from ..abstract_test import AbstractTestCaseWithSeeding
from common.inspection import json_to_python_lambda


class FeatureViewsTests(AbstractTestCaseWithSeeding):
    def feature_assertions(self, feature_result):
        f = Feature.objects.get(id=feature_result.id)
        self.assertEqual(feature_result.id, f.id)
        self.assertEqual(feature_result.name, f.name)

    def test_features_list_view(self):
        c = Client()
        response = c.get('/features', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        features_count = Feature.objects.filter(utility=False).count()
        self.assertEqual(len(result.results), features_count)
        for i in range(features_count):
            self.feature_assertions(result.results[i])

    def test_features_detail_view(self):
        c = Client()
        response = c.get('/features/{}'.format(self.f2_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.f2_id)
        self.feature_assertions(result)
