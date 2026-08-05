from itertools import product
from unittest import TestCase
from spellbook.models.references import FEATURE_REPLACEMENT_PATTERN, format_feature_replacement

KEYS = [
    'Feature',
    'Feature 1',
    'lowercase feature',
    'Feature [x]',
    "Card's ability",
    'Feature with, punctuation',
    'Ünïcödé feature',
]
FACES = [None, '1', '2', '10']
ALIASES = [None, 'alias', 'Alias 2', 'an alias with [brackets]']
SELECTORS = [None, '1', '3', 'Attribute', 'attribute name']
POSTFIX_ALIASES = [None, 'post', 'post alias']


def all_parts():
    return product(KEYS, FACES, ALIASES, SELECTORS, POSTFIX_ALIASES)


class FeatureReplacementPatternTests(TestCase):
    def test_pattern_matches_formatted_replacement(self):
        for key, face, alias, selector, postfix_alias in all_parts():
            with self.subTest(key=key, face=face, alias=alias, selector=selector, postfix_alias=postfix_alias):
                text = format_feature_replacement(key, face, alias, selector, postfix_alias)
                self.assertIsNotNone(FEATURE_REPLACEMENT_PATTERN.fullmatch(text))

    def test_pattern_recovers_the_formatted_parts(self):
        for key, face, alias, selector, postfix_alias in all_parts():
            with self.subTest(key=key, face=face, alias=alias, selector=selector, postfix_alias=postfix_alias):
                text = format_feature_replacement(key, face, alias, selector, postfix_alias)
                match = FEATURE_REPLACEMENT_PATTERN.fullmatch(text)
                assert match is not None
                self.assertEqual(match.group('key'), key)
                self.assertEqual(match.group('face'), face)
                self.assertEqual(match.group('alias'), alias)
                self.assertEqual(match.group('selector'), selector)
                # a postfix alias is only meaningful for a selected replacement, so it is dropped without a selector
                self.assertEqual(match.group('postfix_alias'), postfix_alias if selector is not None else None)

    def test_formatting_back_a_match_leaves_the_text_untouched(self):
        for key, face, alias, selector, postfix_alias in all_parts():
            with self.subTest(key=key, face=face, alias=alias, selector=selector, postfix_alias=postfix_alias):
                replacement = format_feature_replacement(key, face, alias, selector, postfix_alias)
                for text in (replacement, f'before {replacement} after', f'{replacement}{replacement}', f'[[{replacement}]]'):
                    result, count = FEATURE_REPLACEMENT_PATTERN.subn(lambda m: format_feature_replacement(*m.groups()), text)
                    self.assertGreater(count, 0)
                    self.assertEqual(result, text)
