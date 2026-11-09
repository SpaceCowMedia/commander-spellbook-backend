from itertools import product
from unittest import TestCase
from spellbook.models.references import ALIAS_REFERENCE_PATTERN, FEATURE_REFERENCE_PATTERN, LINE_REFERENCE_PATTERN, expand_aliases, format_alias_reference, format_feature_reference, format_line_reference, references_past_copies_needed, references_to_features_not_needed, references_to_unknown_keys, attribute_keys_referenced, referenced_line

FEATURES = [
    'Feature',
    'Feature 1',
    '3 Mana',
    'lowercase feature',
    'Feature (x)',
    "Card's ability",
    'Feature with, punctuation: colons',
    'Creature with +1/+1 counters',
    'Aura that grants {T}: add {W}',
    'Ünïcödé feature',
]
FACES = [None, '1', '2', '10']
SELECTORS = [None, '1', '3', 'Attribute', 'attribute name', 'pow>=4', '+1/+1 counters']
KEYS = [None, 'name', 'mana_needed', 'sac activation', 'Key: with colon']
ALIASES = [None, 'alias', 'Alias 2']


def all_parts():
    return product(FEATURES, FACES, SELECTORS, KEYS, ALIASES)


class FeatureReferencePatternTests(TestCase):
    def test_pattern_recovers_the_formatted_parts(self):
        for parts in all_parts():
            with self.subTest(parts=parts):
                match = FEATURE_REFERENCE_PATTERN.fullmatch(format_feature_reference(*parts))
                assert match is not None
                self.assertEqual(match.groups(), parts)

    def test_formatting_back_a_match_leaves_the_text_untouched(self):
        for parts in all_parts():
            with self.subTest(parts=parts):
                reference = format_feature_reference(*parts)
                for text in (reference, f'before {reference} after', f'{reference}{reference}'):
                    result, count = FEATURE_REFERENCE_PATTERN.subn(lambda m: format_feature_reference(*m.groups()), text)
                    self.assertGreater(count, 0)
                    self.assertEqual(result, text)

    def test_pattern_ignores_the_syntaxes_it_is_not(self):
        for text in (
            format_alias_reference('alias'),
            format_alias_reference('alias', 'key'),
            format_line_reference(3),
            format_line_reference(2, '+'),
            '[[Feature|alias$1]]',
            '[[Feature@key$1]]',
            '[[Feature@key@other]]',
            '[[Feature#face]]',
            '{{Feature}}',
            '[[]]',
        ):
            with self.subTest(text=text):
                self.assertIsNone(FEATURE_REFERENCE_PATTERN.fullmatch(text))


class AliasReferencePatternTests(TestCase):
    def test_pattern_recovers_the_alias_and_the_key(self):
        for alias, key in product(('alias', 'Alias 2'), (None, 'description', 'sac step')):
            with self.subTest(alias=alias, key=key):
                match = ALIAS_REFERENCE_PATTERN.fullmatch(format_alias_reference(alias, key))
                assert match is not None
                self.assertEqual(match.groups(), (alias, key))


class LineReferencePatternTests(TestCase):
    def test_a_reference_points_at_its_line(self):
        for sign, number, line, expected in (('', 3, 5, 3), ('+', 2, 5, 7), ('-', 1, 5, 4)):
            with self.subTest(sign=sign, number=number):
                match = LINE_REFERENCE_PATTERN.fullmatch(format_line_reference(number, sign))
                assert match is not None
                self.assertEqual(referenced_line(match, line), expected)

    def test_a_feature_named_like_a_number_is_no_line_reference(self):
        self.assertIsNone(LINE_REFERENCE_PATTERN.search(format_feature_reference('3')))
        self.assertIsNone(FEATURE_REFERENCE_PATTERN.search(format_line_reference(3)))


class ExpandAliasesTests(TestCase):
    def test_a_use_repeats_the_reference_defining_it(self):
        definition = format_feature_reference('Feature', '2', '1', alias='x')
        text = f'{definition}, then {format_alias_reference("x")} and {format_alias_reference("x", "description")}'
        expected = f'{definition}, then {format_feature_reference("Feature", "2", "1")} and {format_feature_reference("Feature", "2", "1", "description")}'
        self.assertEqual(expand_aliases(text), expected)

    def test_a_use_keeps_the_key_of_its_definition_unless_it_names_another(self):
        definition = format_feature_reference('Feature', key='mana_needed', alias='m')
        text = f'{definition} {format_alias_reference("m")} {format_alias_reference("m", "description")}'
        expected = f'{definition} {format_feature_reference("Feature", key="mana_needed")} {format_feature_reference("Feature", key="description")}'
        self.assertEqual(expand_aliases(text), expected)

    def test_a_use_before_its_definition_is_expanded_too(self):
        text = f'{format_alias_reference("x")} and {format_feature_reference("Feature", alias="x")}'
        self.assertEqual(expand_aliases(text), f'{format_feature_reference("Feature")} and {format_feature_reference("Feature", alias="x")}')

    def test_an_alias_the_text_does_not_define_is_left_as_written(self):
        text = f'{format_alias_reference("y")} and {format_alias_reference("y", "notes")} next to {format_feature_reference("Feature", alias="x")}'
        self.assertEqual(expand_aliases(text), text)


class ReferencesToFeaturesNotNeededTests(TestCase):
    def test_references_to_needed_features_pass(self):
        texts = [
            f'Activate {format_feature_reference("Feature", "2", "1", alias="alias")}, then {format_feature_reference("Other feature", selector="attribute")} and {format_alias_reference("alias")}.',
            f'Include {format_feature_reference("Feature", selector="1", key="description")}.',
        ]
        self.assertEqual(references_to_features_not_needed(texts, {'Feature', 'Other feature'}), [])

    def test_references_to_other_features_are_returned_once_sorted(self):
        texts = ['[[Unneeded]] and [[Included@description]]', '[[Feature]], [[Unneeded]] and [[Another]]']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), ['[[Another]]', '[[Included@description]]', '[[Unneeded]]'])

    def test_names_are_matched_exactly(self):
        self.assertEqual(references_to_features_not_needed(['[[feature]] and [[feature@notes]]'], {'Feature'}), ['[[feature@notes]]', '[[feature]]'])

    def test_an_alias_is_checked_through_its_definition(self):
        texts = [f'{format_feature_reference("Unneeded", alias="alias")} then {format_alias_reference("alias")} and {format_alias_reference("alias", "description")}']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), [format_feature_reference('Unneeded', alias='alias')])

    def test_line_references_are_no_feature_references(self):
        texts = [f'First\nSecond\nBack to {format_line_reference(2, "-")}, forward to {format_line_reference(1, "+")}\nRepeat {format_line_reference(3)}', 'Then [[Unneeded@notes]]']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), ['[[Unneeded@notes]]'])


class ReferencesPastCopiesNeededTests(TestCase):
    def test_positions_among_the_copies_needed_pass(self):
        texts = [f'{format_feature_reference("Feature", selector="1")} and {format_feature_reference("Feature", selector="2", key="description")}, {format_feature_reference("Feature", selector="attribute")}']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 2}), [])

    def test_positions_past_the_copies_needed_are_returned_once_sorted(self):
        texts = ['[[Feature$3]], [[Feature$0@notes]] and [[Feature$3]]', '[[Other$2]]']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 2, 'Other': 1}), ['[[Feature$0@notes]]', '[[Feature$3]]', '[[Other$2]]'])

    def test_a_feature_not_needed_is_left_to_the_other_check(self):
        self.assertEqual(references_past_copies_needed(['[[Unneeded$5]]'], {'Feature': 1}), [])

    def test_an_alias_is_checked_through_its_definition(self):
        texts = [f'{format_feature_reference("Feature", selector="2", alias="x")} then {format_alias_reference("x")}']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 1}), [format_feature_reference('Feature', selector='2', alias='x')])


class ReferencesToUnknownKeysTests(TestCase):
    def test_built_in_keys_and_attributes_pass(self):
        texts = ['[[Outlet]], [[Outlet@description]], [[Outlet$2@mana_needed]] and [[Outlet$Landfall@effect]]']
        self.assertEqual(references_to_unknown_keys(texts, {'effect'}), [])

    def test_keys_that_are_no_attribute_are_returned_once_sorted(self):
        texts = ['[[Outlet@step]], [[Outlet@effect]] and [[Outlet@step]]', '[[Other@mana]]']
        self.assertEqual(references_to_unknown_keys(texts, {'effect'}), ['[[Other@mana]]', '[[Outlet@step]]'])
        self.assertEqual(attribute_keys_referenced(texts), {'step', 'effect', 'mana'})

    def test_alias_uses_are_checked_as_the_reference_they_repeat(self):
        texts = ['[[Outlet$1|outlet]] then [[!outlet@effect]] and [[!outlet@step]]']
        self.assertEqual(references_to_unknown_keys(texts, {'effect'}), ['[[Outlet$1@step]]'])
