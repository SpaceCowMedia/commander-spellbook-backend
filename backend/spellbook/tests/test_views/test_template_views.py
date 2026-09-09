import json
from rest_framework import status
from django.urls import reverse
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Template
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

    def test_templates_matches_filter(self):
        # the templates a card stands in for include the ones a query found it, not only the ones listing it
        query_template = Template.objects.create(name='TC', scryfall_query='t:creature')
        response = self.client.get(reverse('templates-list') + '?matches=' + str(self.c3_id), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertSetEqual({t.id for t in result.results}, {self.t2_id, query_template.id})
        for template_result in result.results:
            self.template_assertions(template_result)

    def test_templates_matches_filter_names_the_card_by_its_number(self):
        '''The filter takes the id the API publishes for a card, which is its number, not its key.

        A seeded card carries a number equal to its key, so the two only tell apart on a card given a
        number of its own, the way a card curated after the number existed gets one.'''
        card = Card.objects.create(name='Numbered Card', number=900, type_line='Creature', legal_commander=True)
        self.assertNotEqual(card.pk, card.number)
        self.assertFalse(Card.objects.filter(number=card.pk).exists())
        query_template = Template.objects.create(name='TC', scryfall_query='t:creature')
        response = self.client.get(reverse('templates-list') + '?matches=' + str(card.number), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertIn(query_template.id, {t.id for t in result.results})
        response = self.client.get(reverse('templates-list') + '?matches=' + str(card.pk), follow=True)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
