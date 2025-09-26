import json
from rest_framework import status
from django.urls import reverse
from common.inspection import json_to_python_lambda
from spellbook.models import Template
from ..testing import SpellbookTestCaseWithSeeding


class TemplateViewsTests(SpellbookTestCaseWithSeeding):
    def template_assertions(self, template_result):
        t = Template.objects.get(id=template_result.id)
        self.assertEqual(template_result.id, t.id)
        self.assertEqual(template_result.name, t.name)
        self.assertEqual(template_result.scryfall_query, t.scryfall_query)
        self.assertEqual(template_result.scryfall_api, t.scryfall_api())

    def test_templates_list_view(self):
        response = self.client.get(reverse('templates-list'), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        template_count = Template.objects.count()
        self.assertEqual(len(result.results), template_count)
        for i in range(template_count):
            self.template_assertions(result.results[i])

    def test_templates_detail_view(self):
        response = self.client.get(reverse('templates-detail', args=[self.t1_id]), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.t1_id)
        self.template_assertions(result)
