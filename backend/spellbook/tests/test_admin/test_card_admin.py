from django.urls import reverse
from spellbook.models import Card
from ..testing import SpellbookTestCaseWithSeeding


class CardAdminTests(SpellbookTestCaseWithSeeding):
    def test_changelist_view(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_card_changelist'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'{Card.objects.get(number=self.c1_id).name}</a>', str(response.content))

    def test_changelist_view_with_facets(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('admin:spellbook_card_changelist'), query_params={'_facets': 'True'})  # type: ignore
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'?_facets=True&amp;identity=C', response.content)

    def test_autocomplete_offers_curated_cards_by_number(self):
        self.client.force_login(self.admin)
        curated = Card.objects.get(number=self.c1_id)
        uncurated = Card.objects.create(name='Uncurated Card', type_line='Instant')
        response = self.client.get(reverse('admin:autocomplete'), query_params={  # type: ignore
            'app_label': 'spellbook',
            'model_name': 'cardincombo',
            'field_name': 'card',
            'term': 'a',
        })
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        ids = {result['id'] for result in results}
        self.assertIn(str(curated.number), ids)
        self.assertNotIn(str(uncurated.pk), ids)

    def test_change_view_offers_the_curate_button_only_when_uncurated(self):
        self.client.force_login(self.admin)
        uncurated = Card.objects.create(name='Card To Curate', type_line='Instant')
        response = self.client.get(reverse('admin:spellbook_card_change', args=[uncurated.pk]))
        self.assertContains(response, '<span class="button__text">Curate this card, so that combos and templates can use it</span>')
        self.assertNotContains(response, '<div class="actions">')
        curated = Card.objects.get(number=self.c1_id)
        response = self.client.get(reverse('admin:spellbook_card_change', args=[curated.pk]))
        self.assertNotContains(response, '<span class="button__text">Curate this card')

    def test_curate_action_assigns_the_next_number(self):
        self.client.force_login(self.admin)
        last = Card.objects.order_by('-number').first()
        assert last is not None and last.number is not None
        uncurated = Card.objects.create(name='Card To Curate', type_line='Instant')
        response = self.post_object_tool(Card, uncurated.pk, 'curate')
        self.assertRedirects(response, reverse('admin:spellbook_card_change', args=[uncurated.pk]), fetch_redirect_response=False)
        uncurated.refresh_from_db()
        self.assertEqual(uncurated.number, last.number + 1)

    def test_curate_action_ignores_get_requests(self):
        self.client.force_login(self.admin)
        uncurated = Card.objects.create(name='Card To Curate', type_line='Instant')
        response = self.client.get(reverse('admin:spellbook_card_change', args=[uncurated.pk]), {'CHANGE_FORM-action': 'curate', '_selected_action': str(uncurated.pk)})
        self.assertEqual(response.status_code, 200)
        uncurated.refresh_from_db()
        self.assertIsNone(uncurated.number)

    def test_curate_action_curates_the_selected_cards_from_the_changelist(self):
        self.client.force_login(self.admin)
        last = Card.objects.order_by('-number').first()
        assert last is not None and last.number is not None
        first = Card.objects.create(name='A Card To Curate', type_line='Instant')
        second = Card.objects.create(name='B Card To Curate', type_line='Instant')
        curated = Card.objects.get(number=self.c1_id)
        response = self.client.post(reverse('admin:spellbook_card_changelist'), {'action': 'curate', '_selected_action': [first.pk, second.pk, curated.pk]}, follow=True)
        self.assertEqual(response.status_code, 200)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual((first.number, second.number), (last.number + 1, last.number + 2))
        messages = [str(m) for m in response.context['messages']]
        self.assertIn(f'Curated A Card To Curate as card number {first.number}, B Card To Curate as card number {second.number}.', messages)
        self.assertIn(f'Already curated: {curated.name} as card number {curated.number}.', messages)
