from importlib import import_module
from unittest import TestCase
from django.apps import apps
from spellbook.models import CardInCombo, Combo, Feature, FeatureAttribute, FeatureNeededInCombo, ZoneLocation
from .testing import SpellbookTestCase, curated_card

# A migration converts between the syntaxes of its time, so its tests write both as they were
reference_prefixes = import_module('spellbook.migrations.0081_reference_prefixes')
dictionaries = import_module('spellbook.migrations.0083_dictionaries')
FSO = ('Free Sacrifice Outlet', None, None)


def convert(text: str, defined_elsewhere: dict | None = None, feature_names: tuple[str, ...] = ()) -> str:
    return reference_prefixes.convert_text(text, (defined_elsewhere or {}).get, feature_names)


class ReferencePrefixesConversionTests(TestCase):
    def test_line_references_gain_their_prefix(self):
        self.assertEqual(convert('Step {{3}}, then {{+1}} and {{-2}}, not {{Feature}}.'), 'Step {{#3}}, then {{#+1}} and {{#-2}}, not {{Feature}}.')

    def test_an_alias_used_by_the_text_defining_it_gains_its_prefix(self):
        self.assertEqual(convert('[[sister]] then [[Gain life|sister]] and [[sister]]'), '[[!sister]] then [[Gain life|sister]] and [[!sister]]')
        self.assertEqual(convert('[[Feature#2$1|x]] and [[x]]'), '[[Feature#2$1|x]] and [[!x]]')

    def test_a_definition_repeating_the_first_one_becomes_a_use(self):
        self.assertEqual(convert('[[Blinker|blinker]] then [[Blinker|blinker]]'), '[[Blinker|blinker]] then [[!blinker]]')
        self.assertEqual(convert('[[Blinker|blinker]] then [[Other|blinker]]'), '[[Blinker|blinker]] then [[Other|blinker]]')

    def test_the_first_use_of_an_alias_defined_elsewhere_defines_it(self):
        self.assertEqual(convert('[[FSO]] then [[FSO]]', {'FSO': FSO}), '[[Free Sacrifice Outlet|FSO]] then [[!FSO]]')

    def test_a_feature_and_an_unresolved_alias_are_left_as_written(self):
        self.assertEqual(convert('[[FSO]] and [[ETS]]', {'FSO': FSO}, ('FSO',)), '[[FSO]] and [[ETS]]')

    def test_forms_without_an_equivalent_are_left_as_written(self):
        self.assertEqual(convert('[[Feature|x$1|y]] and [[Feature|z]] then [[z$2]]'), '[[Feature|x$1|y]] and [[Feature|z]] then [[z$2]]')


class ReferencePrefixesMigrationTests(SpellbookTestCase):
    def test_texts_are_converted_and_reverted(self):
        defining = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Free Sacrifice Outlet|FSO]] then [[FSO]].\nRepeat from step {{1}}.')
        using = Combo.objects.create(status=Combo.Status.UTILITY, description='Activate [[FSO]].', notes='Back to {{-1}}')
        state = CardInCombo.objects.create(combo=using, card=curated_card(name='Migration Card'), order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='as in step {{+1}}')

        reference_prefixes.convert_references(apps, None)

        defining.refresh_from_db()
        using.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(defining.description, '[[Free Sacrifice Outlet|FSO]] then [[!FSO]].\nRepeat from step {{#1}}.')
        self.assertEqual((using.description, using.notes), ('Activate [[Free Sacrifice Outlet|FSO]].', 'Back to {{#-1}}'))
        self.assertEqual(state.battlefield_card_state, 'as in step {{#+1}}')

        reference_prefixes.revert_references(apps, None)

        defining.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual(defining.description, '[[Free Sacrifice Outlet|FSO]] then [[FSO]].\nRepeat from step {{1}}.')
        self.assertEqual(state.battlefield_card_state, 'as in step {{+1}}')


class DictionariesConversionTests(TestCase):
    def test_an_inclusion_becomes_a_reference_to_the_key_of_its_field(self):
        self.assertEqual(dictionaries.convert_text('First {{FSO}}, then {{FSO$2}}.', 'description'), 'First [[FSO@description]], then [[FSO$2@description]].')
        self.assertEqual(dictionaries.convert_text('{{FSO}} on the battlefield', 'battlefield_card_state'), '[[FSO@battlefield_card_state]] on the battlefield')

    def test_an_alias_inclusion_keeps_its_alias(self):
        self.assertEqual(dictionaries.convert_text('[[FSO|outlet]] then {{!outlet}}', 'notes'), '[[FSO|outlet]] then [[!outlet@notes]]')

    def test_a_line_reference_takes_square_brackets(self):
        self.assertEqual(dictionaries.convert_text('Step {{#3}}, then {{#+1}} and {{#-2}}.', 'description'), 'Step [[#3]], then [[#+1]] and [[#-2]].')

    def test_replacements_and_symbols_are_left_as_written(self):
        text = 'Pay {2}{U} to activate [[FSO$2|outlet]] and [[!outlet]].'
        self.assertEqual(dictionaries.convert_text(text, 'description'), text)

    def test_reverting_undoes_the_keys_of_its_own_field_only(self):
        text = 'First {{FSO}}, {{!a}}, step {{#+1}}'
        converted = dictionaries.convert_text(text, 'description')
        self.assertEqual(dictionaries.revert_text(converted, 'description'), text)
        self.assertEqual(dictionaries.revert_text('[[FSO@mana_needed]] and [[FSO@sac step]]', 'description'), '[[FSO@mana_needed]] and [[FSO@sac step]]')

    def test_an_inclusion_in_a_description_references_what_the_card_descriptions_became(self):
        keys = {'Blood': ('effect',), 'FSO': ('effect', 'description')}
        text = '[[FSO|outlet]] then {{!outlet}}, {{FSO$2}}, {{Blood}} and {{Plain}}'
        converted = dictionaries.convert_text(text, 'description', keys)
        self.assertEqual(converted, '[[FSO|outlet]] then [[!outlet@effect]][[!outlet@description]], [[FSO$2@effect]][[FSO$2@description]], [[Blood@effect]] and [[Plain@description]]')
        self.assertEqual(dictionaries.revert_text(converted, 'description'), text)
        self.assertEqual(dictionaries.convert_text('{{Blood}}', 'notes', keys), '[[Blood@notes]]')
        self.assertEqual(dictionaries.revert_text('[[Blood@effect]]', 'notes'), '[[Blood@effect]]')


class DictionariesMigrationTests(SpellbookTestCase):
    def test_texts_are_converted_and_reverted(self):
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='First {{FSO}}.\nRepeat from step {{#1}}.', notes='{{FSO$1}}')
        state = CardInCombo.objects.create(combo=combo, card=curated_card(name='Migration Card'), order=1, zone_locations=ZoneLocation.BATTLEFIELD, battlefield_card_state='as {{FSO}} asks')

        dictionaries.convert_references(apps, None)

        combo.refresh_from_db()
        state.refresh_from_db()
        self.assertEqual((combo.description, combo.notes), ('First [[FSO@description]].\nRepeat from step [[#1]].', '[[FSO$1@notes]]'))
        self.assertEqual(state.battlefield_card_state, 'as [[FSO@battlefield_card_state]] asks')

        dictionaries.revert_references(apps, None)

        combo.refresh_from_db()
        self.assertEqual(combo.description, 'First {{FSO}}.\nRepeat from step {{#1}}.')

    def test_inclusions_follow_the_producers_with_an_effect_or_a_description(self):
        blood, outlet = Feature.objects.create(name='Blood'), Feature.objects.create(name='Outlet')
        effect = FeatureAttribute.objects.create(name='effect')
        card = curated_card(name='Migration Card')
        for feature in (blood, outlet):
            card.featureofcard_set.create(feature=feature, zone_locations=ZoneLocation.BATTLEFIELD).attributes.add(effect, through_defaults={'value': 'adding {C}'})
        Combo.objects.create(status=Combo.Status.UTILITY, description='adding {B}{R}').produces.add(outlet)
        Combo.objects.create(status=Combo.Status.UTILITY).produces.add(blood)
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='{{Blood}}, {{Outlet}} and {{FSO}}', notes='{{Blood}}')

        dictionaries.convert_references(apps, None)

        combo.refresh_from_db()
        self.assertEqual(combo.description, '[[Blood@effect]], [[Outlet@effect]][[Outlet@description]] and [[FSO@description]]')
        self.assertEqual(combo.notes, '[[Blood@notes]]')

    def test_the_keys_in_use_become_attributes(self):
        outlet = Feature.objects.create(name='Outlet')
        FeatureAttribute.objects.create(name='effect')
        combo = Combo.objects.create(status=Combo.Status.UTILITY, description='[[Outlet|outlet]] then [[Outlet@mana]], [[!outlet@sac step]] and [[Outlet@description]]')
        FeatureNeededInCombo.objects.create(combo=combo, feature=outlet, order=1, dictionary={'name': '', 'effect': 'it', 'step': ['first']})

        dictionaries.create_key_attributes(apps, None)

        self.assertEqual(sorted(FeatureAttribute.objects.values_list('name', flat=True)), ['effect', 'mana', 'sac step', 'step'])

    def test_names_holding_reserved_characters_stop_the_migration(self):
        dictionaries.refuse_reserved_names(apps, None)
        Feature.objects.create(name='Feature @ reserved')
        FeatureAttribute.objects.create(name='attribute | reserved')
        with self.assertRaisesMessage(RuntimeError, 'Feature "Feature @ reserved", FeatureAttribute "attribute | reserved"'):
            dictionaries.refuse_reserved_names(apps, None)
