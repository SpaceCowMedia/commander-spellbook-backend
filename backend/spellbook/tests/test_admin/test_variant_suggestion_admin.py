from django.urls import reverse
from ..testing import SpellbookTestCaseWithSeeding


class VariantSuggestionAdminTests(SpellbookTestCaseWithSeeding):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def card_form_count(self, url: str) -> int:
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        formset = next(inline.formset for inline in response.context['inline_admin_formsets'] if inline.formset.prefix == 'uses')
        return formset.total_form_count()

    def test_an_existing_suggestion_shows_only_its_cards(self):
        self.assertEqual(self.card_form_count(reverse('admin:spellbook_variantsuggestion_change', args=[self.s1_id])), 2)
