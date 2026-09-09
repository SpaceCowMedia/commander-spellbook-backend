from django.urls import reverse
from spellbook.models import Template
from ..testing import SpellbookTestCaseWithSeeding


class TemplateAdminTests(SpellbookTestCaseWithSeeding):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def template_payload(self, **overrides) -> dict:
        payload = {
            'name': 'Test Template',
            'scryfall_query': 't:instant',
            'description': '',
            'templatereplacement_set-TOTAL_FORMS': '0',
            'templatereplacement_set-INITIAL_FORMS': '0',
            'templatereplacement_set-MIN_NUM_FORMS': '0',
            'templatereplacement_set-MAX_NUM_FORMS': '1000',
        }
        payload.update(overrides)
        return payload

    def test_a_query_naming_a_card_is_saved(self):
        response = self.client.post(reverse('admin:spellbook_template_add'), data=self.template_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Template.objects.latest('created').matches.count(), 1)

    def test_a_query_naming_no_card_is_rejected(self):
        template_count = Template.objects.count()
        response = self.client.post(reverse('admin:spellbook_template_add'), data=self.template_payload(scryfall_query='o:"no card says this"'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('matches no card', response.content.decode())
        self.assertEqual(Template.objects.count(), template_count)

    def test_a_query_naming_only_a_card_outside_commander_is_saved(self):
        # the seeded planeswalker is the one card no commander deck may play, and the check ignores that
        response = self.client.post(reverse('admin:spellbook_template_add'), data=self.template_payload(scryfall_query='t:planeswalker'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Template.objects.latest('created').matches.count(), 0)

    def test_an_unreadable_query_is_still_rejected_as_such(self):
        response = self.client.post(reverse('admin:spellbook_template_add'), data=self.template_payload(scryfall_query='t:instant ('))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('matches no card', response.content.decode())
