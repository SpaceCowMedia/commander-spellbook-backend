import re
from collections import defaultdict
from html import unescape
from django.urls import reverse
from spellbook.admin.combo_admin import ALL_ZONE_LOCATIONS
from spellbook.models import Combo, CardInCombo, ZoneLocation
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes
from ..testing import SpellbookTestCaseWithSeeding


INLINE_PREFIXES = [
    'cardincombo_set',
    'templateincombo_set',
    'featureneededincombo_set',
    'featureproducedincombo_set',
    'featureremovedincombo_set',
]


class ComboAdminTestCase(SpellbookTestCaseWithSeeding):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def combo_payload(self, cards: list[int], card_ids_to_update: list[int] = [], zone_locations: str = ZoneLocation.BATTLEFIELD, **overrides) -> dict:
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
                f'cardincombo_set-{i}-zone_locations': zone_locations,
                f'cardincombo_set-{i}-order': str(i + 1),
                f'cardincombo_set-{i}-in_replacements': 'on',
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


class ComboAdminUtilityComboTests(ComboAdminTestCase):
    '''Utility combos don't restrict the zones their ingredients start in, so their starting locations can be left blank.'''

    def test_blank_starting_locations_are_saved_as_every_zone(self):
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c7_id],
            zone_locations='',
            status=Combo.Status.UTILITY,
        ))
        self.assertEqual(response.status_code, 302)
        added_combo = Combo.objects.latest('created')
        self.assertEqual(added_combo.cardincombo_set.get().zone_locations, ALL_ZONE_LOCATIONS)

    def test_blank_starting_locations_are_rejected_on_other_combos(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c7_id],
            zone_locations='',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn('This field is required', response.content.decode())
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_starting_locations_can_be_cleared_on_an_existing_utility_combo(self):
        '''The seeded combo b5 is a utility combo requiring the cards c5 and c6.'''
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        response = self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=card_ids,
            zone_locations='',
            status=Combo.Status.UTILITY,
        ))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(Combo.objects.get(id=self.b5_id).cardincombo_set.values_list('zone_locations', flat=True)),
            {ALL_ZONE_LOCATIONS},
        )

    def test_chosen_starting_locations_are_left_alone(self):
        response = self.client.post(self.add_url(), data=self.combo_payload(
            cards=[self.c7_id],
            zone_locations=ZoneLocation.GRAVEYARD,
            status=Combo.Status.UTILITY,
        ))
        self.assertEqual(response.status_code, 302)
        added_combo = Combo.objects.latest('created')
        self.assertEqual(added_combo.cardincombo_set.get().zone_locations, ZoneLocation.GRAVEYARD)


class ComboAdminReplacementsTests(ComboAdminTestCase):
    '''At least one ingredient has to be in replacements, or the features the combo produces would
    have nothing to be replaced with in the texts referencing them.'''
    rejection_message = 'none of its ingredients is in replacements'

    def test_a_combo_with_one_ingredient_in_replacements_is_saved(self):
        payload = self.combo_payload(cards=[self.c7_id, self.c8_id])
        payload['cardincombo_set-1-in_replacements'] = ''
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 302)
        added_combo = Combo.objects.latest('created')
        self.assertEqual({c.card_id: c.in_replacements for c in added_combo.cardincombo_set.all()}, {self.c7_id: True, self.c8_id: False})

    def test_a_combo_with_no_ingredient_in_replacements_is_rejected(self):
        combo_count = Combo.objects.count()
        payload = self.combo_payload(cards=[self.c7_id, self.c8_id])
        payload['cardincombo_set-0-in_replacements'] = ''
        payload['cardincombo_set-1-in_replacements'] = ''
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.rejection_message, response.content.decode())
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_a_needed_feature_alone_in_replacements_is_enough(self):
        payload = self.combo_payload(cards=[self.c7_id])
        payload['cardincombo_set-0-in_replacements'] = ''
        payload.update({
            'featureneededincombo_set-TOTAL_FORMS': '1',
            'featureneededincombo_set-0-feature': str(self.f2_id),
            'featureneededincombo_set-0-quantity': '1',
            'featureneededincombo_set-0-order': '1',
            'featureneededincombo_set-0-in_replacements': 'on',
        })
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 302)
        added_combo = Combo.objects.latest('created')
        self.assertFalse(added_combo.cardincombo_set.get().in_replacements)
        self.assertTrue(added_combo.featureneededincombo_set.get().in_replacements)

    def test_a_combo_without_ingredients_is_left_alone(self):
        '''Nothing to opt out of yet, so this check stays quiet.'''
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(cards=[]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.count(), combo_count + 1)


class ComboAdminMultipleCopiesTests(ComboAdminTestCase):
    '''A combo can require more than one copy of a card or template only if it allows multiple copies.'''
    rejection_message = 'Cannot require more than one copy of the same card or template'

    def added_combo_payload(self, quantity: str, **overrides) -> dict:
        '''The data of an added combo requiring the given quantity of the card c7.'''
        payload = self.combo_payload(cards=[self.c7_id], **overrides)
        payload['cardincombo_set-0-quantity'] = quantity
        return payload

    def changed_combo_payload(self, quantity: str, **overrides) -> dict:
        '''The data of a change to the seeded utility combo b5, requiring the given quantity of its first card c5.'''
        payload = self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True)),
            status=Combo.Status.UTILITY,
            **overrides,
        )
        payload['cardincombo_set-0-quantity'] = quantity
        return payload

    def template_payload(self, quantity: str, **overrides) -> dict:
        '''The data of an added combo requiring the given quantity of the template t1.'''
        payload = self.combo_payload(cards=[self.c7_id], **overrides)
        payload.update({
            'templateincombo_set-TOTAL_FORMS': '1',
            'templateincombo_set-0-template': str(self.t1_id),
            'templateincombo_set-0-quantity': quantity,
            'templateincombo_set-0-zone_locations': ZoneLocation.BATTLEFIELD,
            'templateincombo_set-0-order': '1',
            'templateincombo_set-0-in_replacements': 'on',
        })
        return payload

    def allow_two_copies_of_c5_in_b5(self):
        Combo.objects.filter(id=self.b5_id).update(allow_multiple_copies=True)
        CardInCombo.objects.filter(combo_id=self.b5_id, card_id=self.c5_id).update(quantity=2)

    def test_multiple_copies_of_a_card_are_rejected_without_the_option(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.added_combo_payload(quantity='2'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.rejection_message, response.content.decode())
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_multiple_copies_of_a_card_are_saved_with_the_option(self):
        response = self.client.post(self.add_url(), data=self.added_combo_payload(quantity='2', allow_multiple_copies='on'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.latest('created').cardincombo_set.get().quantity, 2)

    def test_a_single_copy_of_a_card_does_not_need_the_option(self):
        response = self.client.post(self.add_url(), data=self.added_combo_payload(quantity='1'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.latest('created').cardincombo_set.get().quantity, 1)

    def test_multiple_copies_of_a_template_are_rejected_without_the_option(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.template_payload(quantity='2'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.rejection_message, response.content.decode())
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_multiple_copies_of_a_template_are_saved_with_the_option(self):
        response = self.client.post(self.add_url(), data=self.template_payload(quantity='2', allow_multiple_copies='on'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.latest('created').templateincombo_set.get().quantity, 2)

    def test_multiple_copies_of_a_needed_feature_are_saved_without_the_option(self):
        '''The option is about cards and templates: needed features are always allowed in multiple copies.'''
        payload = self.combo_payload(cards=[self.c7_id])
        payload.update({
            'featureneededincombo_set-TOTAL_FORMS': '1',
            'featureneededincombo_set-0-feature': str(self.f2_id),
            'featureneededincombo_set-0-quantity': '2',
            'featureneededincombo_set-0-order': '1',
        })
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.latest('created').featureneededincombo_set.get().quantity, 2)

    def test_the_option_can_be_enabled_together_with_the_quantity(self):
        '''The seeded combo b5 requires the cards c5 and c6 in one copy, without allowing multiple copies.'''
        response = self.client.post(self.change_url(self.b5_id), data=self.changed_combo_payload(quantity='2', allow_multiple_copies='on'))
        self.assertEqual(response.status_code, 302)
        combo = Combo.objects.get(id=self.b5_id)
        self.assertTrue(combo.allow_multiple_copies)
        self.assertEqual(combo.cardincombo_set.get(card_id=self.c5_id).quantity, 2)

    def test_disabling_the_option_while_a_card_needs_multiple_copies_is_rejected(self):
        self.allow_two_copies_of_c5_in_b5()
        response = self.client.post(self.change_url(self.b5_id), data=self.changed_combo_payload(quantity='2'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.rejection_message, response.content.decode())
        self.assertTrue(Combo.objects.get(id=self.b5_id).allow_multiple_copies, 'The combo must not be changed.')

    def test_the_option_can_be_disabled_together_with_the_quantity(self):
        self.allow_two_copies_of_c5_in_b5()
        response = self.client.post(self.change_url(self.b5_id), data=self.changed_combo_payload(quantity='1'))
        self.assertEqual(response.status_code, 302)
        combo = Combo.objects.get(id=self.b5_id)
        self.assertFalse(combo.allow_multiple_copies)
        self.assertEqual(combo.cardincombo_set.get(card_id=self.c5_id).quantity, 1)

    def test_deleted_cards_do_not_need_the_option(self):
        self.allow_two_copies_of_c5_in_b5()
        payload = self.changed_combo_payload(quantity='2')
        payload['cardincombo_set-0-DELETE'] = 'on'
        response = self.client.post(self.change_url(self.b5_id), data=payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(Combo.objects.get(id=self.b5_id).uses.values_list('id', flat=True)), {self.c6_id})


class ComboAdminDuplicateConfirmationTests(ComboAdminTestCase):
    '''The seeded combo b4 requires the cards c8 and c1, while b5 requires c5 and c6.'''

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

    def test_a_duplicate_combo_with_invalid_data_shows_the_form_with_its_errors(self):
        combo_count = Combo.objects.count()
        payload = self.combo_payload(cards=[self.c5_id, self.c6_id], mana_needed='not a mana cost')
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateNotUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html')
        self.assertTemplateUsed(response, 'admin/spellbook/combo/change_form.html')
        content = response.content.decode()
        self.assertIn('This combo was not saved', content)
        self.assertIn('This combo would still be a duplicate of 1 other combo', content)
        self.assertIn(f'>{self.b5_id}</a>', content)
        self.assertEqual(Combo.objects.count(), combo_count)

        response = self.client.post(self.add_url(), data={**payload, 'mana_needed': '{W}'})
        self.assertTemplateUsed(response, 'admin/spellbook/combo/duplicate_confirmation.html', 'The confirmation page must appear once the errors are fixed.')
        self.assertEqual(Combo.objects.count(), combo_count)

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
