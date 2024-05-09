import json
from django.test import Client
from spellbook.models import Template
from ..abstract_test import AbstractTestCaseWithSeeding
from common.inspection import json_to_python_lambda


class TemplateViewsTests(AbstractTestCaseWithSeeding):
    def template_assertions(self, template_result):
        t = Template.objects.get(id=template_result.id)
        self.assertEqual(template_result.id, t.id)
        self.assertEqual(template_result.name, t.name)
        self.assertEqual(template_result.scryfall_query, t.scryfall_query)
        self.assertEqual(template_result.scryfall_api, t.scryfall_api())

    def test_templates_list_view(self):
        c = Client()
        response = c.get('/templates', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        templates_count = Template.objects.count()
        self.assertEqual(len(result.results), templates_count)
        for i in range(templates_count):
            self.template_assertions(result.results[i])

    def test_templates_detail_view(self):
        c = Client()
        response = c.get('/templates/{}'.format(self.t1_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.t1_id)
        self.template_assertions(result)
