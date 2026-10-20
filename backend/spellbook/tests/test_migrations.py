from importlib import import_module
from unittest import TestCase
from django.apps import apps
from spellbook.models import CardInCombo, Combo, ZoneLocation
from .testing import SpellbookTestCase, curated_card

# A migration converts between the syntaxes of its time, so its tests write both as they were
reference_prefixes = import_module('spellbook.migrations.0081_reference_prefixes')
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
