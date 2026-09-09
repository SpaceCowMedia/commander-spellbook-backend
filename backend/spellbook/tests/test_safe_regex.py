from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from spellbook.parsers.safe_regex import MAX_REGEX_LENGTH, MAX_REPETITION, validate_query_regexes, validate_safe_regex

# the regular expressions the templates in production are written with
PRODUCTION_PATTERNS = [
    r'^cycling (\{B\}|\{1\}|\{2\})$',
    r'^cycling \{1\}\{B\}$',
    r'^cycling (\{1\}|\sc)$',
    r'^Sacrifice a Goblin:',
    r'^{T}: Add ',
    r'^{T}: Add',
    r'^Equip \{2\}\sc',
    r'^Equip \{1\}\sc',
    r'^Equip \{3\}\sc',
]

# the shapes catastrophic backtracking is made of
DANGEROUS_PATTERNS = [
    r'(a+)+',
    r'(a*)*',
    r'(a|a)*',
    r'(a|b)+',
    r'(?:x+)+',
    r'([a-z]+)*z',
    r'(a{2,4})+',
    r'(\w+\s?)*$',
]


class SafeRegexTests(SimpleTestCase):
    def test_the_patterns_the_templates_are_written_with_are_accepted(self):
        for pattern in PRODUCTION_PATTERNS:
            with self.subTest(pattern=pattern):
                validate_safe_regex(pattern)

    def test_a_repeated_group_that_repeats_or_chooses_within_itself_is_refused(self):
        for pattern in DANGEROUS_PATTERNS:
            with self.subTest(pattern=pattern):
                with self.assertRaises(ValidationError):
                    validate_safe_regex(pattern)

    def test_a_group_is_allowed_to_choose_when_nothing_repeats_it(self):
        validate_safe_regex(r'(a|b)c')
        validate_safe_regex(r'(a+)b')
        validate_safe_regex(r'a+b+c+')

    def test_a_brace_is_a_repetition_only_when_a_digit_follows_it(self):
        # a query writes a mana symbol without escaping it, and {T} is not a repetition of anything
        validate_safe_regex(r'^{T}: Add')
        validate_safe_regex(r'(a){' + str(MAX_REPETITION) + '}')
        with self.assertRaises(ValidationError):
            validate_safe_regex(r'(a){' + str(MAX_REPETITION + 1) + '}')
        with self.assertRaises(ValidationError):
            validate_safe_regex(r'a{1,' + str(MAX_REPETITION + 1) + '}')

    def test_back_references_are_refused(self):
        with self.assertRaises(ValidationError):
            validate_safe_regex(r'(a)\1')

    def test_lookarounds_are_refused(self):
        for pattern in (r'(?=a)b', r'(?!a)b', r'(?<=a)b', r'(?P<name>a)'):
            with self.subTest(pattern=pattern):
                with self.assertRaises(ValidationError):
                    validate_safe_regex(pattern)
        validate_safe_regex(r'(?:a)b')

    def test_a_pattern_that_does_not_compile_is_refused(self):
        with self.assertRaises(ValidationError):
            validate_safe_regex(r'(a')

    def test_an_overlong_pattern_is_refused(self):
        validate_safe_regex('a' * MAX_REGEX_LENGTH)
        with self.assertRaises(ValidationError):
            validate_safe_regex('a' * (MAX_REGEX_LENGTH + 1))

    def test_a_quantifier_inside_a_character_class_is_not_one(self):
        validate_safe_regex(r'([*+?]+)a')

    def test_the_tilde_a_query_writes_for_the_card_name_is_counted(self):
        # the tilde becomes a quantifier of its own, so repeating a group holding one is refused
        with self.assertRaises(ValidationError):
            validate_query_regexes(r'o:/(~)+/')
        validate_query_regexes(r'o:/^~ enters tapped$/')

    def test_a_query_carrying_a_dangerous_pattern_is_refused(self):
        with self.assertRaises(ValidationError):
            validate_query_regexes(r't:creature o:/(a+)+/')
        validate_query_regexes(r't:creature o:/^cycling (\{B\}|\{1\})$/')

    def test_a_query_without_any_pattern_is_accepted(self):
        validate_query_regexes('t:creature mv<=2 -o:"enters tapped"')

    def test_the_slashes_of_card_text_are_not_a_pattern(self):
        # every template naming a +1/+1 counter carries slashes that begin no regular expression
        validate_query_regexes('t:creature o:"enters with" o:"five +1/+1 counters" -o:kicker')
        validate_query_regexes('o:"+1/+1 counter on it for each" or o:"+1/+1 counters on it for each"')
