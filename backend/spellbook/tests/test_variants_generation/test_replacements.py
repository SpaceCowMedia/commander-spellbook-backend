from itertools import product
from unittest import TestCase
from spellbook.models.references import FEATURE_INCLUSION_PATTERN, FEATURE_REPLACEMENT_PATTERN, LINE_REFERENCE_PATTERN, expand_aliases, format_alias_inclusion, format_alias_replacement, format_feature_inclusion, format_feature_replacement, format_line_reference, references_past_copies_needed, references_to_features_not_needed, referenced_line

KEYS = [
    'Feature',
    'Feature 1',
    '3 Mana',
    'lowercase feature',
    'Feature [x]',
    "Card's ability",
    'Feature with, punctuation',
    'Ünïcödé feature',
]
FACES = [None, '1', '2', '10']
SELECTORS = [None, '1', '3', 'Attribute', 'attribute name']
ALIASES = [None, 'alias', 'Alias 2']


def all_parts():
    return product(KEYS, FACES, SELECTORS, ALIASES)


def all_inclusion_parts():
    return product(KEYS, SELECTORS)


class FeatureReplacementPatternTests(TestCase):
    def test_pattern_recovers_the_formatted_parts(self):
        for key, face, selector, alias in all_parts():
            with self.subTest(key=key, face=face, selector=selector, alias=alias):
                match = FEATURE_REPLACEMENT_PATTERN.fullmatch(format_feature_replacement(key, face, selector, alias))
                assert match is not None
                self.assertEqual(match.groups(), (key, face, selector, alias))

    def test_formatting_back_a_match_leaves_the_text_untouched(self):
        for key, face, selector, alias in all_parts():
            with self.subTest(key=key, face=face, selector=selector, alias=alias):
                replacement = format_feature_replacement(key, face, selector, alias)
                for text in (replacement, f'before {replacement} after', f'{replacement}{replacement}', f'[[{replacement}]]'):
                    result, count = FEATURE_REPLACEMENT_PATTERN.subn(lambda m: format_feature_replacement(*m.groups()), text)
                    self.assertGreater(count, 0)
                    self.assertEqual(result, text)

    def test_pattern_ignores_the_syntaxes_it_is_not(self):
        for text in (format_alias_replacement('alias'), format_feature_inclusion('Feature'), '[[Feature|alias$1]]', '[[Feature|alias$1|post]]'):
            with self.subTest(text=text):
                self.assertIsNone(FEATURE_REPLACEMENT_PATTERN.fullmatch(text))


class FeatureInclusionPatternTests(TestCase):
    def test_pattern_recovers_the_formatted_parts(self):
        for key, selector in all_inclusion_parts():
            with self.subTest(key=key, selector=selector):
                match = FEATURE_INCLUSION_PATTERN.fullmatch(format_feature_inclusion(key, selector))
                assert match is not None
                self.assertEqual(match.groups(), (key, selector))

    def test_formatting_back_a_match_leaves_the_text_untouched(self):
        for key, selector in all_inclusion_parts():
            with self.subTest(key=key, selector=selector):
                inclusion = format_feature_inclusion(key, selector)
                for text in (inclusion, f'before {inclusion} after', f'{inclusion}{inclusion}'):
                    result, count = FEATURE_INCLUSION_PATTERN.subn(lambda m: format_feature_inclusion(*m.groups()), text)
                    self.assertGreater(count, 0)
                    self.assertEqual(result, text)

    def test_pattern_ignores_the_syntaxes_it_is_not(self):
        for text in ('{{}}', '{{unpaired}', '{W}', '[[Feature]]', '{{Feature|alias}}', '{{Feature$1$2}}', format_alias_inclusion('alias'), format_line_reference(3), format_line_reference(2, '+')):
            with self.subTest(text=text):
                self.assertIsNone(FEATURE_INCLUSION_PATTERN.search(text))


class LineReferencePatternTests(TestCase):
    def test_a_reference_points_at_its_line(self):
        for sign, number, line, expected in (('', 3, 5, 3), ('+', 2, 5, 7), ('-', 1, 5, 4)):
            with self.subTest(sign=sign, number=number):
                match = LINE_REFERENCE_PATTERN.fullmatch(format_line_reference(number, sign))
                assert match is not None
                self.assertEqual(referenced_line(match, line), expected)

    def test_a_feature_named_like_a_number_is_no_line_reference(self):
        self.assertIsNone(LINE_REFERENCE_PATTERN.search(format_feature_inclusion('3')))


class ExpandAliasesTests(TestCase):
    def test_a_use_repeats_the_reference_defining_it(self):
        definition = format_feature_replacement('Feature', '2', '1', 'x')
        text = f'{definition}, then {format_alias_replacement("x")} and {format_alias_inclusion("x")}'
        expected = f'{definition}, then {format_feature_replacement("Feature", "2", "1")} and {format_feature_inclusion("Feature", "1")}'
        self.assertEqual(expand_aliases(text), expected)

    def test_a_use_before_its_definition_is_expanded_too(self):
        text = f'{format_alias_replacement("x")} and {format_feature_replacement("Feature", alias="x")}'
        self.assertEqual(expand_aliases(text), f'{format_feature_replacement("Feature")} and {format_feature_replacement("Feature", alias="x")}')

    def test_an_alias_the_text_does_not_define_is_left_as_written(self):
        text = f'{format_alias_replacement("y")} and {format_alias_inclusion("y")} next to {format_feature_replacement("Feature", alias="x")}'
        self.assertEqual(expand_aliases(text), text)


class ReferencesToFeaturesNotNeededTests(TestCase):
    def test_references_to_needed_features_pass(self):
        texts = [
            f'Activate {format_feature_replacement("Feature", "2", "1", "alias")}, then {format_feature_replacement("Other feature", selector="attribute")} and {format_alias_replacement("alias")}.',
            f'Include {format_feature_inclusion("Feature", "1")}.',
        ]
        self.assertEqual(references_to_features_not_needed(texts, {'Feature', 'Other feature'}), [])

    def test_references_to_other_features_are_returned_once_sorted(self):
        texts = ['[[Unneeded]] and {{Included}}', '[[Feature]], [[Unneeded]] and [[Another]]']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), ['[[Another]]', '[[Unneeded]]', '{{Included}}'])

    def test_names_are_matched_exactly(self):
        self.assertEqual(references_to_features_not_needed(['[[feature]] and {{feature}}'], {'Feature'}), ['[[feature]]', '{{feature}}'])

    def test_an_alias_is_checked_through_its_definition(self):
        texts = [f'{format_feature_replacement("Unneeded", alias="alias")} then {format_alias_replacement("alias")} and {format_alias_inclusion("alias")}']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), [format_feature_replacement('Unneeded', alias='alias')])

    def test_line_references_are_no_inclusions(self):
        texts = [f'First\nSecond\nBack to {format_line_reference(2, "-")}, forward to {format_line_reference(1, "+")}\nRepeat {format_line_reference(3)}', 'Then {{Unneeded}}']
        self.assertEqual(references_to_features_not_needed(texts, {'Feature'}), ['{{Unneeded}}'])


class ReferencesPastCopiesNeededTests(TestCase):
    def test_positions_among_the_copies_needed_pass(self):
        texts = [f'{format_feature_replacement("Feature", selector="1")} and {format_feature_inclusion("Feature", "2")}, {format_feature_replacement("Feature", selector="attribute")}']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 2}), [])

    def test_positions_past_the_copies_needed_are_returned_once_sorted(self):
        texts = ['[[Feature$3]], {{Feature$0}} and [[Feature$3]]', '[[Other$2]]']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 2, 'Other': 1}), ['[[Feature$3]]', '[[Other$2]]', '{{Feature$0}}'])

    def test_a_feature_not_needed_is_left_to_the_other_check(self):
        self.assertEqual(references_past_copies_needed(['[[Unneeded$5]]'], {'Feature': 1}), [])

    def test_an_alias_is_checked_through_its_definition(self):
        texts = [f'{format_feature_replacement("Feature", selector="2", alias="x")} then {format_alias_replacement("x")}']
        self.assertEqual(references_past_copies_needed(texts, {'Feature': 1}), [format_feature_replacement('Feature', selector='2', alias='x')])
