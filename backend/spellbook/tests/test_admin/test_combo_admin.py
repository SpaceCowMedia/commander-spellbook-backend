import json
import re
from collections import defaultdict
from html import unescape
from django.contrib.auth.models import Permission, User
from django.urls import reverse
from spellbook.admin.combo_admin import ALL_ZONE_LOCATIONS
from spellbook.models import Card, CardInCombo, CardUsedInVariantSuggestion, Combo, Explanation, FeatureAttribute, FeatureProducedInCombo, FeatureProducedInVariantSuggestion, Variant, VariantSuggestion, ZoneLocation
from spellbook.models.references import format_alias_reference, format_line_reference
from spellbook.admin.utils import AttributesWidget
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes
from ..testing import SpellbookTestCaseWithSeeding, save_dictionary


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


class ComboAdminAttributesWidgetTests(ComboAdminTestCase):
    def test_the_change_page_shows_a_summary_of_the_attributes_of_every_produced_feature(self):
        produced = FeatureProducedInCombo.objects.filter(combo_id=self.b2_id).first()
        save_dictionary(produced, {'step': 'untap it', 'Landfall': None})
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        self.assertIn('admin/js/dictionary_editor.js', content)
        self.assertIn('admin/js/js-yaml/4.1.0/js-yaml.min.js', content)
        self.assertIn('<span class="dictionary-keys">FA2, Landfall, step</span><span class="dictionary-count" title="3 attributes">3</span>', content)

    def test_the_editor_edits_the_explanation_of_every_produced_feature_with_its_own_widgets(self):
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        editor = re.search(r'name="featureproducedincombo_set-0-attribute_texts".*?<button', content, re.DOTALL)
        assert editor is not None
        for field in Explanation.explanation_fields():
            with self.subTest(field=field):
                self.assertNotIn(f'class="column-{field}', content)
                self.assertIn(f'name="featureproducedincombo_set-0-{field}"', editor[0])
        self.assertIn('<input type="checkbox" name="featureproducedincombo_set-0-is_mana_needed_an_accurate_minimum"', editor[0])
        self.assertIn('<textarea name="featureproducedincombo_set-0-description"', editor[0])

    def test_who_cannot_change_the_produced_features_reads_their_explanation_in_columns(self):
        viewer = User.objects.create_user(username='viewer', is_staff=True)
        viewer.user_permissions.add(*Permission.objects.filter(codename__in=['view_combo', 'view_featureproducedincombo']))
        self.client.force_login(viewer)
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        for field in Explanation.explanation_fields():
            with self.subTest(field=field):
                self.assertIn(f'class="column-{field}', content)

    def test_the_summary_names_the_texts_written_before_the_attributes(self):
        produced = FeatureProducedInCombo.objects.filter(combo_id=self.b2_id).first()
        save_dictionary(produced, {'notes': 'an engine', 'step': 'untap it'})
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        self.assertIn('<span class="dictionary-keys"><em class="dictionary-written-text">Notes</em>, FA2, step</span><span class="dictionary-count" title="2 attributes">2</span>', content)

    def test_an_added_row_starts_with_no_attributes(self):
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        self.assertIn('name="featureproducedincombo_set-__prefix__-attribute_texts"', content)
        self.assertNotIn('Invalid, edit to fix', content)

    def test_an_added_row_left_blank_is_ignored(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.combo_payload(cards=[self.c1_id], **{
            'featureproducedincombo_set-TOTAL_FORMS': '1',
            'featureproducedincombo_set-0-feature': '',
            'featureproducedincombo_set-0-is_mana_needed_an_accurate_minimum': 'on',
            'featureproducedincombo_set-0-attribute_texts': '{}',
        }))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Combo.objects.count(), combo_count + 1)

    def test_the_editor_links_each_attribute_to_the_admin_as_far_as_the_user_may_use_it(self):
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        for link in ('change_id___key__', 'add_id___key__', 'view_id___key__'):
            self.assertIn(link, content)
        self.assertIn(f'href="{reverse("admin:spellbook_featureattribute_add")}?_to_field=name&amp;_popup=1"', content)
        viewer = User.objects.create_user(username='viewer', is_staff=True)
        viewer.user_permissions.add(*Permission.objects.filter(codename__in=['view_combo', 'change_combo', 'view_featureproducedincombo', 'change_featureproducedincombo', 'view_featureattribute']))
        self.client.force_login(viewer)
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        self.assertIn('view_id___key__', content)
        self.assertNotIn('change_id___key__', content)
        self.assertNotIn('add_id___key__', content)

    def test_the_editor_picks_the_attributes_from_the_autocomplete_of_the_admin(self):
        content = self.client.get(self.change_url(self.b2_id)).content.decode()
        self.assertIn('admin/js/vendor/select2/select2.full', content)
        source = re.search(r'data-autocomplete-url="([^"]+)" data-app-label="([^"]+)" data-model-name="([^"]+)" data-field-name="([^"]+)"', content)
        assert source is not None
        url, app_label, model_name, field_name = source.groups()
        response = self.client.get(url, query_params={'app_label': app_label, 'model_name': model_name, 'field_name': field_name, 'term': 'FA'})  # type: ignore
        self.assertEqual(response.status_code, 200)
        self.assertCountEqual([result['text'] for result in response.json()['results']], ['FA1', 'FA2'])

    def test_submitted_texts_are_normalized_like_the_other_texts(self):
        widget = AttributesWidget()
        value = widget.value_from_datadict({'attributes': '{"step": "Sacrifice it’s target", "Landfall": null}'}, {}, 'attributes')
        self.assertEqual(json.loads(value), {'step': "Sacrifice it's target", 'Landfall': None})

    def test_an_invalid_submission_is_left_for_the_form_to_refuse(self):
        widget = AttributesWidget()
        for submitted in ('not json', '{"key": 3}', '["a list"]', '{"key": ["a list"]}'):
            with self.subTest(submitted=submitted):
                self.assertEqual(widget.value_from_datadict({'attributes': submitted}, {}, 'attributes'), submitted)
        self.assertIn('Invalid, edit to fix', widget.render('attributes', 'not json'))


class ComboAdminReferencesTests(ComboAdminTestCase):
    '''The texts of a combo can only reference the features it requires, by their exact names, since
    those are the ones its variants are sure to replace, and each text can repeat them by the aliases
    it defines.'''

    def payload_requiring(self, features: list[int], **overrides) -> dict:
        payload = self.combo_payload(cards=[self.c7_id], **overrides)
        payload['featureneededincombo_set-TOTAL_FORMS'] = str(len(features))
        for i, feature_id in enumerate(features):
            payload.update({
                f'featureneededincombo_set-{i}-feature': str(feature_id),
                f'featureneededincombo_set-{i}-quantity': '1',
                f'featureneededincombo_set-{i}-order': str(i + 1),
                f'featureneededincombo_set-{i}-in_replacements': 'on',
            })
        return payload

    def assertSaved(self, payload: dict):
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 302)

    def assertRejected(self, payload: dict, *references: str, problem: str = 'reference features it does not require'):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'its texts {problem}: {", ".join(references)}.', unescape(response.content.decode()))
        self.assertEqual(Combo.objects.count(), combo_count)

    def assertPositionsRejected(self, payload: dict, *references: str):
        self.assertRejected(payload, *references, problem='select copies of features it does not require')

    def test_a_reference_to_a_required_feature_is_saved(self):
        self.assertSaved(self.payload_requiring([self.f2_id], description='Activate [[FB]].'))

    def test_a_reference_to_a_feature_not_required_is_rejected(self):
        self.assertRejected(self.payload_requiring([], description='Activate [[FB]].'), '[[FB]]')

    def test_names_are_matched_exactly(self):
        self.assertRejected(self.payload_requiring([self.f2_id], description='Activate [[fb]].'), '[[fb]]')

    def test_a_long_list_of_references_is_cut_short(self):
        references = sorted(f'[[Unneeded {i}]]' for i in range(12))
        response = self.client.post(self.add_url(), data=self.payload_requiring([], description=' '.join(references)))
        self.assertIn(f'its texts reference features it does not require: {", ".join(references[:10])} and 2 more.', unescape(response.content.decode()))

    def test_an_alias_can_be_used_and_included_by_the_text_defining_it(self):
        self.assertSaved(self.payload_requiring(
            [self.f2_id],
            description=f'When it enters, [[FB|outlet]] triggers.\nActivate {format_alias_reference("outlet")}.\n{format_alias_reference("outlet", "description")}',
        ))

    def test_an_alias_can_be_named_like_a_feature(self):
        self.assertSaved(self.payload_requiring([self.f2_id], description=f'[[FB|FC]] triggers, then {format_alias_reference("FC")} resolves.'))

    def test_an_alias_another_text_defines_is_rejected(self):
        combo_count = Combo.objects.count()
        response = self.client.post(self.add_url(), data=self.payload_requiring(
            [self.f2_id],
            easy_prerequisites='[[FB|outlet]] on the battlefield.',
            description=f'Activate {format_alias_reference("outlet")}.',
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn(f'{format_alias_reference("outlet")} uses an alias this text does not define.', unescape(response.content.decode()))
        self.assertEqual(Combo.objects.count(), combo_count)

    def test_a_key_of_a_feature_not_required_is_rejected(self):
        self.assertRejected(self.payload_requiring([], description='[[FB@description]]'), '[[FB@description]]')

    def payload_producing(self, payload: dict, **fields: str) -> dict:
        '''The payload of a combo producing FD, with the given fields on its produced row.'''
        payload.update({
            'featureproducedincombo_set-TOTAL_FORMS': '1',
            'featureproducedincombo_set-0-feature': str(self.f4_id),
            'featureproducedincombo_set-0-is_mana_needed_an_accurate_minimum': 'on',
            **{f'featureproducedincombo_set-0-{field}': value for field, value in fields.items()},
        })
        return payload

    def test_a_produced_row_keeps_its_texts_and_its_attributes_apart(self):
        FeatureAttribute.objects.create(name='step')
        FeatureAttribute.objects.create(name='Landfall')
        self.assertSaved(self.payload_producing(self.payload_requiring([]), notes='an engine', attribute_texts='{"step": "untap it", "Landfall": null}'))
        combo = Combo.objects.latest('created')
        produced = combo.featureproducedincombo_set.get()
        self.assertEqual(produced.notes, 'an engine')
        self.assertEqual(sorted(produced.attributes.through.objects.filter(producer=produced).values_list('attribute__name', 'value')), [('Landfall', ''), ('step', 'untap it')])
        content = unescape(self.client.get(self.change_url(combo.id)).content.decode())
        self.assertIn('{"Landfall": null, "step": "untap it"}', content)

    def test_a_produced_row_holds_existing_attributes_only(self):
        response = self.client.post(self.add_url(), data=self.payload_producing(self.payload_requiring([]), attribute_texts='{"step": "untap it"}'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('These are no attributes: step. Create them as attributes first.', unescape(response.content.decode()))

    def test_a_key_written_is_built_in_or_an_attribute(self):
        payload = self.payload_requiring([self.f2_id], description='Sacrifice it[[FB@effect]], naming [[FB]], [[FB@description]].')
        self.assertRejected(payload, '[[FB@effect]]', problem='write keys that are no feature attribute')
        FeatureAttribute.objects.create(name='effect')
        self.assertSaved(payload)

    def test_the_texts_and_attributes_of_the_produced_features_are_checked_too(self):
        FeatureAttribute.objects.create(name='sac step')
        self.assertRejected(self.payload_producing(self.payload_requiring([self.f3_id]), attribute_texts='{"sac step": "Sacrifice [[FB]]"}'), '[[FB]]')
        self.assertRejected(self.payload_producing(self.payload_requiring([self.f3_id]), description='Sacrifice [[FB]]'), '[[FB]]')

    def test_line_references_are_saved(self):
        self.assertSaved(self.payload_requiring([], description='\n'.join(f'Step {i}' for i in range(1, 8)) + f'\nBack to {format_line_reference(5, "-")}, then {format_line_reference(7)}.'))

    def test_the_states_of_the_ingredients_are_checked_too(self):
        payload = self.payload_requiring([self.f3_id])
        payload['cardincombo_set-0-battlefield_card_state'] = 'Enchanted by [[FB]].'
        self.assertRejected(payload, '[[FB]]')

    def test_a_position_among_the_copies_required_is_saved(self):
        self.assertSaved(self.payload_requiring([self.f2_id, self.f2_id], description='Activate [[FB$1]], then [[FB$2@description]].'))

    def test_a_position_past_the_copies_required_is_rejected(self):
        self.assertPositionsRejected(self.payload_requiring([self.f2_id], description='Activate [[FB$2]], then [[FB$0]].'), '[[FB$0]]', '[[FB$2]]')

    def test_the_quantity_of_a_row_counts_its_copies(self):
        payload = self.payload_requiring([self.f2_id], description='Activate [[FB$2]].')
        payload['featureneededincombo_set-0-quantity'] = '2'
        self.assertSaved(payload)

    def test_an_uncountable_feature_is_a_single_copy(self):
        self.assertPositionsRejected(self.payload_requiring([self.f5_id, self.f5_id], description='Activate [[FE$2]].'), '[[FE$2]]')

    def test_a_deleted_required_feature_no_longer_counts(self):
        payload = self.payload_requiring([self.f2_id], description='Activate [[FB]].')
        payload['featureneededincombo_set-0-DELETE'] = 'on'
        self.assertRejected(payload, '[[FB]]')


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
        self.assertEqual(set(Combo.objects.get(id=self.b5_id).uses.values_list('number', flat=True)), {self.c6_id})


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
        self.assertEqual(set(added_combo.uses.values_list('number', flat=True)), {self.c5_id, self.c6_id})

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
        self.assertEqual(set(added_combo.uses.values_list('number', flat=True)), {self.c5_id, self.c6_id})
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
            set(Combo.objects.get(id=self.b5_id).uses.values_list('number', flat=True)),
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
            set(Combo.objects.get(id=self.b5_id).uses.values_list('number', flat=True)),
            {self.c5_id, self.c6_id},
            'The combo must not be changed before the editor confirms.',
        )

        response = self.client.post(self.change_url(self.b5_id), data={**payload, '_confirm_duplicate': 'Yes, I’m sure'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(set(Combo.objects.get(id=self.b5_id).uses.values_list('number', flat=True)), {self.c8_id, self.c1_id})


class ComboAdminRestoreTests(ComboAdminTestCase):
    '''A variant writes the texts of every combo it includes, so saving one has to flag them all
    for restore, not only the ones the combo generates. An utility combo generates none.'''

    def save_b5(self):
        card_ids = list(CardInCombo.objects.filter(combo_id=self.b5_id).order_by('order').values_list('id', flat=True))
        return self.client.post(self.change_url(self.b5_id), data=self.combo_payload(
            cards=[self.c5_id, self.c6_id],
            card_ids_to_update=card_ids,
            status=Combo.Status.UTILITY,
            description='An edited description',
        ))

    def test_saving_an_utility_combo_restores_the_new_variants_including_it(self):
        self.generate_variants()
        including = set(Variant.objects.filter(includes=self.b5_id).values_list('id', flat=True))
        self.assertTrue(including)
        self.assertFalse(Variant.objects.filter(of=self.b5_id).exists())
        Variant.objects.update(status=Variant.Status.NEW)
        response = self.save_b5()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(Variant.objects.filter(status=Variant.Status.RESTORE).values_list('id', flat=True)),
            including,
        )

    def test_published_variants_are_left_alone(self):
        self.generate_and_publish_variants()
        self.assertTrue(Variant.objects.filter(includes=self.b5_id).exists())
        response = self.save_b5()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Variant.objects.filter(status=Variant.Status.RESTORE).exists())


class ComboFromSuggestionTests(SpellbookTestCaseWithSeeding):
    '''Accepting a suggestion that names a card the database holds but no editor has curated.'''

    def _add_form_from(self, card_name: str):
        self.client.force_login(self.admin)
        suggestion = VariantSuggestion.objects.create(
            status=VariantSuggestion.Status.NEW,
            description='d',
            suggested_by=self.admin,
        )
        CardUsedInVariantSuggestion.objects.create(suggestion=suggestion, card=card_name, order=1, zone_locations=ZoneLocation.BATTLEFIELD)
        FeatureProducedInVariantSuggestion.objects.create(suggestion=suggestion, feature='FA')
        return self.client.get(reverse('admin:spellbook_combo_add'), query_params={'from_variant_suggestion': suggestion.pk}, follow=True)  # type: ignore

    def test_an_uncurated_card_is_reported_instead_of_leaving_the_row_blank(self):
        uncurated = Card.objects.create(name='Uncurated Suggested Card', type_line='Instant')
        response = self._add_form_from(uncurated.name)
        self.assertEqual(response.status_code, 200)
        messages = [str(m) for m in response.context['messages']]
        self.assertTrue(any('has not been curated' in message for message in messages), messages)

    def test_a_curated_card_is_filled_in(self):
        curated = Card.objects.filter(number__isnull=False).first()
        assert curated is not None
        response = self._add_form_from(curated.name)
        self.assertEqual(response.status_code, 200)
        messages = [str(m) for m in response.context['messages']]
        self.assertFalse(any('has not been curated' in message for message in messages), messages)
