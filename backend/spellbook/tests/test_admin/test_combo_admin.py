import re
from collections import defaultdict
from html import unescape
from django.urls import reverse
from spellbook.models import Combo, CardInCombo
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes
from ..testing import SpellbookTestCaseWithSeeding


INLINE_PREFIXES = [
    'cardincombo_set',
    'templateincombo_set',
    'featureneededincombo_set',
    'featureproducedincombo_set',
    'featureremovedincombo_set',
]


class ComboAdminDuplicateConfirmationTests(SpellbookTestCaseWithSeeding):
    '''The seeded combo b4 requires the cards c8 and c1, while b5 requires c5 and c6.'''

    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def combo_payload(self, cards: list[int], card_ids_to_update: list[int] = [], **overrides) -> dict:
        '''Build the data of a submitted combo add/change form, requiring the given cards.'''
        payload: dict = {
            'mana_needed': '',
            'is_mana_needed_an_accurate_minimum': 'on',
            'easy_prerequisites': '',
            'notable_prerequisites': '',
            'status': Combo.Status.DRAFT,
            'description': 'Test Description',
            'notes': '',
            'comment': '',
        }
        for prefix in INLINE_PREFIXES:
            payload.update({
                f'{prefix}-TOTAL_FORMS': '0',
                f'{prefix}-INITIAL_FORMS': '0',
                f'{prefix}-MIN_NUM_FORMS': '0',
                f'{prefix}-MAX_NUM_FORMS': '1000',
            })
        for i, card in enumerate(cards):
            payload.update({
                f'cardincombo_set-{i}-card': str(card),
                f'cardincombo_set-{i}-quantity': '1',
                f'cardincombo_set-{i}-zone_locations': 'B',
                f'cardincombo_set-{i}-order': str(i + 1),
            })
            if i < len(card_ids_to_update):
                payload[f'cardincombo_set-{i}-id'] = str(card_ids_to_update[i])
        payload['cardincombo_set-TOTAL_FORMS'] = str(len(cards))
        payload['cardincombo_set-INITIAL_FORMS'] = str(len(card_ids_to_update))
        payload.update(overrides)
        return payload

    def add_url(self) -> str:
        return reverse('admin:spellbook_combo_add')

    def change_url(self, combo_id: int) -> str:
        return reverse('admin:spellbook_combo_change', args=[combo_id])

    def test_adding_a_unique_combo_does_not_ask_for_confirmation(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(cards=[self.c7_id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.count(), combo_count + 1)

    def test_adding_a_duplicate_combo_asks_for_confirmation(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(cards=[self.c5_id, self.c6_id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html')
        content = response.content.decode()
        self.assertIn('Would you still like to add this combo?', content)
        self.assertIn(f'{self.b5_id}:', content)
        self.assertEqual(Combo.objects.count(), combo_count, 'The combo must not be added before the editor confirms.')

    def test_confirming_a_duplicate_combo_adds_it(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            _confirm_duplicate='Yes, I’m sure',
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.count(), combo_count + 1)
        added_combo = Combo.objects.latest('created')
        self.assertEqual(set(added_combo.uses.values_list('id', flat=True)), {self.c5_id, self.c6_id})

    def test_the_data_carried_by_the_confirmation_page_is_added_unchanged(self):
        '''The confirmation page round trips the submitted data through hidden inputs, the way a browser would resubmit it.'''
        description = 'Line one\r\nLine two with an apostrophe\'s "quotes" & <angles>'
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            description=description,
        ))
        confirmed_payload = defaultdict[str, list[str]](list)
        for name, value in re.findall(r'<input type="hidden" name="([^"]*)" value="([^"]*)">', response.content.decode(), re.DOTALL):
            confirmed_payload[unescape(name)].append(unescape(value))
        self.assertIn('description', confirmed_payload)
        confirmed_payload['_confirm_duplicate'].append('Yes, I’m sure')

        response = self.client.post(self.add_url(), data=confirmed_payload)
        self.assertEqual(response.status_code, 302)
        added_combo = Combo.objects.latest('created')
        self.assertEqual(set(added_combo.uses.values_list('id', flat=True)), {self.c5_id, self.c6_id})
        self.assertEqual(added_combo.description, sanitize_newlines_apostrophes_and_quotes(description), 'The description must survive the confirmation page.')

    def test_cancelling_a_duplicate_combo_goes_back_to_the_form_without_adding_it(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            _cancel_duplicate='1',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html')
        self.assertTemplateUsed(response, 'admin/spellbook/combo/change_form.html')
        content = response.content.decode()
        self.assertIn('This combo was not saved', content)
        self.assertIn(f'>{self.b5_id}</a>', content)
        self.assertEqual(Combo.objects.count(), combo_count, 'The combo must not be added after the editor cancels.')

    def test_the_confirmation_page_preserves_the_submitted_data(self):
        payload = self.combo_payload(cards=[self.c5_id, self.c6_id], description='Some description to preserve')
        response = self.client.post(self.add_url(), data=payload)
        content = response.content.decode()
        self.assertIn('<input type="hidden" name="description" value="Some description to preserve">', content)
        self.assertIn(f'<input type="hidden" name="cardincombo_set-0-card" value="{self.c5_id}">', content)
        self.assertIn(f'<input type="hidden" name="cardincombo_set-1-card" value="{self.c6_id}">', content)

    def test_saving_a_combo_without_making_it_a_duplicate_does_not_ask_for_confirmation(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        response = self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
        ))
        self.assertEqual(response.status_code, 302, 'A combo is never a duplicate of itself.')

    def test_saving_as_new_with_invalid_data_shows_the_form_again(self):
        '''Django renders the change template for a rejected "save as new", even though there is no original combo to link tools to.'''
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        response = self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c7_id],
            card_ids_to_update=card_ids,
            mana_needed='not a mana cost',
            _saveasnew='Save as new',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/spellbook/combo/change_form.html')

    def test_cancelling_a_duplicate_change_goes_back_to_the_form_without_saving_it(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        response = self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c8_id, self.c1_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
            _cancel_duplicate='1',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/spellbook/combo/change_form.html')
        self.assertIn('This combo was not saved', response.content.decode())
        self.assertEqual(
            set(Combo.objects.get(id=self.b5_id).uses.values_list('id', flat=True)),
            {self.c5_id, self.c6_id},
            'The combo must not be changed after the editor cancels.',
        )

    def test_cancelling_a_duplicate_save_as_new_goes_back_to_the_form(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        combo_count = Combo.objects.count()
        response = self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
            _saveasnew='Save as new',
            _cancel_duplicate='1',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn('This combo was not saved', response.content.decode())
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_saving_a_combo_as_new_asks_for_confirmation(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        combo_count = Combo.objects.count()
        payload = self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
            _saveasnew='Save as new',
        )
        response = self.client.post(self.change_url(self.b5_id), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html')
        content = response.content.decode()
        self.assertIn('Would you still like to add this combo?', content, 'Saving as new adds a combo.')
        self.assertIn(f'{self.b5_id}:', content, 'The combo it is copied from is the duplicate.')
        self.assertEqual(Combo.objects.count(), combo_count)

        response = self.client.post(self.change_url(self.b5_id), data={**payload, '_confirm_duplicate': 'Yes, I’m sure'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.count(), combo_count + 1)

    def test_changing_a_combo_into_a_duplicate_asks_for_confirmation(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        payload = self.combo_payload(
            cards=[self.c8_id, self.c1_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
        )
        response = self.client.post(self.change_url(self.b5_id), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html')
        content = response.content.decode()
        self.assertIn('Would you still like to save this combo?', content)
        self.assertIn(f'{self.b4_id}:', content)
        self.assertEqual(
            set(Combo.objects.get(id=self.b5_id).uses.values_list('id', flat=True)),
            {self.c5_id, self.c6_id},
            'The combo must not be changed before the editor confirms.',
        )

        response = self.client.post(self.change_url(self.b5_id), data={**payload, '_confirm_duplicate': 'Yes, I’m sure'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(Combo.objects.get(id=self.b5_id).uses.values_list('id', flat=True)), {self.c8_id, self.c1_id})
