from collections import Counter
from typing import Any, Callable
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible
from ..regexs import URL_REGEX, FIRST_CAPITAL_LETTER_REGEX, FIRST_CAPITAL_LETTER_OR_DIGIT_REGEX, NO_TRAILING_PUNCTUATION_REGEX, MANA_REGEX, DOUBLE_SQUARE_BRACKET_TEXT_REGEX, SYMBOLS_TEXT_REGEX, ORDINARY_CHARACTERS_REGEX
from .references import ALIAS_REFERENCE_PATTERN, ATTRIBUTE_NAME_RESERVED_CHARACTERS, ATTRIBUTE_NAME_RESERVED_CHARACTERS_REGEX, BUILT_IN_KEYS, CARD_STATE_KEYS, FEATURE_NAME_RESERVED_CHARACTERS, FEATURE_NAME_RESERVED_CHARACTERS_REGEX, FEATURE_REFERENCE_PATTERN, LINE_REFERENCE_PATTERN, REFERENCE_PATTERN, RESERVED_CHARACTERS, RESERVED_CHARACTERS_REGEX, TEXT_KEYS, expand_aliases, feature_references, format_alias_reference, format_feature_reference, format_line_reference, key_of, referenced_line
from ..parsers.scryfall_query_grammar import SCRYFALL_GRAMMAR, VARIABLES_SUPPORTED
from ..parsers.lark_validator import LarkGrammarValidator
from ..parsers.safe_regex import MAX_REGEX_LENGTH, validate_query_regexes

NOT_URL_VALIDATOR = RegexValidator(regex=URL_REGEX, inverse_match=True, message='URLs are not allowed.')

FIRST_CAPITAL_LETTER_VALIDATOR = RegexValidator(regex=FIRST_CAPITAL_LETTER_REGEX, message='Must start with a capital letter.')

FIRST_CAPITAL_LETTER_OR_DIGIT_VALIDATOR = RegexValidator(regex=FIRST_CAPITAL_LETTER_OR_DIGIT_REGEX, message='Must start with a capital letter or a digit.')

NO_TRAILING_PUNCTUATION_VALIDATOR = RegexValidator(regex=NO_TRAILING_PUNCTUATION_REGEX, message='Must not end with punctuation.')

MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.')

DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

ORDINARY_CHARACTERS_VALIDATOR = RegexValidator(regex=ORDINARY_CHARACTERS_REGEX, message='Only ordinary characters are allowed.')

NO_RESERVED_CHARACTERS_VALIDATOR = RegexValidator(regex=RESERVED_CHARACTERS_REGEX, inverse_match=True, message=f'Reserved characters are not allowed. Examples of reserved characters: {", ".join(RESERVED_CHARACTERS)}.')

NO_FEATURE_NAME_RESERVED_CHARACTERS_VALIDATOR = RegexValidator(regex=FEATURE_NAME_RESERVED_CHARACTERS_REGEX, inverse_match=True, message=f'Must not contain {" ".join(FEATURE_NAME_RESERVED_CHARACTERS)}, which delimit the parts of a reference.')

NO_ATTRIBUTE_NAME_RESERVED_CHARACTERS_VALIDATOR = RegexValidator(regex=ATTRIBUTE_NAME_RESERVED_CHARACTERS_REGEX, inverse_match=True, message=f'Must not contain {" ".join(ATTRIBUTE_NAME_RESERVED_CHARACTERS)}, which delimit the parts of a reference.')


@deconstructible
class ReferencesValidator:
    '''Rejects a text holding anything but a reference between double brackets, an alias used without
    being defined once in the same text, or a line reference pointing at a line the text does not have.'''
    code = 'invalid'
    syntax = (
        f'Write a feature as {format_feature_reference("feature", "face", "selector", "key", "alias")},'
        ' where only the feature is required, an alias the same text defines as'
        f' {format_alias_reference("alias")} or {format_alias_reference("alias", key="key")},'
        f' and a line as {format_line_reference(3)}, {format_line_reference(2, "+")} or {format_line_reference(1, "-")}.'
    )

    def __call__(self, value: str) -> None:
        defined = Counter(match['alias'] for match in FEATURE_REFERENCE_PATTERN.finditer(value) if match['alias'])
        if twice := sorted(alias for alias, count in defined.items() if count > 1):
            raise ValidationError(f'An alias can be defined only once in a text: {", ".join(twice)}.', code=self.code)
        for reference in REFERENCE_PATTERN.finditer(value):
            if use := ALIAS_REFERENCE_PATTERN.fullmatch(reference[0]):
                if use['alias'] not in defined:
                    raise ValidationError(f'{reference[0]} uses an alias this text does not define.', code=self.code)
            elif not any(pattern.fullmatch(reference[0]) for pattern in (FEATURE_REFERENCE_PATTERN, LINE_REFERENCE_PATTERN)):
                raise ValidationError(f'{reference[0]} is not a reference. {self.syntax}', code=self.code)
        lines = value.split('\n')
        for position, line in enumerate(lines, start=1):
            for reference in LINE_REFERENCE_PATTERN.finditer(line):
                if not 1 <= referenced_line(reference, position) <= len(lines):
                    raise ValidationError(f'{reference[0]} on line {position} points at a line the text does not have.', code=self.code)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReferencesValidator)


REFERENCES_VALIDATOR = ReferencesValidator()

TEXT_VALIDATORS: list[Callable[[Any], None]] = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR, ORDINARY_CHARACTERS_VALIDATOR, REFERENCES_VALIDATOR]
NAME_BODY_VALIDATORS: list[Callable[[Any], None]] = [NO_TRAILING_PUNCTUATION_VALIDATOR, NOT_URL_VALIDATOR, NO_RESERVED_CHARACTERS_VALIDATOR, *TEXT_VALIDATORS]
NAME_VALIDATORS: list[Callable[[Any], None]] = [FIRST_CAPITAL_LETTER_VALIDATOR, *NAME_BODY_VALIDATORS]
FEATURE_NAME_VALIDATORS: list[Callable[[Any], None]] = [FIRST_CAPITAL_LETTER_OR_DIGIT_VALIDATOR, NO_FEATURE_NAME_RESERVED_CHARACTERS_VALIDATOR, *NAME_BODY_VALIDATORS]


def not_a_built_in_key(name: str) -> None:
    if name.lower() in BUILT_IN_KEYS:
        raise ValidationError(f'"{name}" is a key every producer provides, which no attribute can be named after.')


ATTRIBUTE_NAME_VALIDATORS: list[Callable[[Any], None]] = [NO_ATTRIBUTE_NAME_RESERVED_CHARACTERS_VALIDATOR, not_a_built_in_key]


def validate_attributes(value: Any) -> None:
    '''Accepts what a producer gives its attributes: a mapping of the names of existing attributes to a
    single valid text, or to nothing. A text is written inline, where no text of a variant can be
    included, so it can only reference names and keys of its own kind.'''
    from .constants import MAX_ATTRIBUTE_VALUE_LENGTH
    from .feature_attribute import FeatureAttribute
    if not isinstance(value, dict):
        raise ValidationError('The attributes must map their names to a text, or to nothing.', code=ATTRIBUTES_CODE)
    for name, text in value.items():
        if name in BUILT_IN_KEYS:
            raise ValidationError(f'"{name}" is no attribute: write it in its own field.', code=ATTRIBUTES_CODE)
        if text is None:
            continue
        if not isinstance(text, str):
            raise ValidationError(f'The text of "{name}" must be a single text, or nothing.', code=ATTRIBUTES_CODE)
        if len(text) > MAX_ATTRIBUTE_VALUE_LENGTH:
            raise ValidationError(f'The text of "{name}" holds more than {MAX_ATTRIBUTE_VALUE_LENGTH} characters.', code=ATTRIBUTES_CODE)
        try:
            for validator in TEXT_VALIDATORS:
                validator(text)
        except ValidationError as error:
            raise ValidationError(f'The text of "{name}" is not valid: {" ".join(error.messages)}', code=ATTRIBUTES_CODE)
        if included := sorted({reference[0] for reference in feature_references([expand_aliases(text)]) if key_of(reference) in TEXT_KEYS + CARD_STATE_KEYS}):
            raise ValidationError(f'The text of "{name}" cannot write texts, being written inline: {", ".join(included)}.', code=ATTRIBUTES_CODE)
    if value and (unknown := sorted(set(value) - set(FeatureAttribute.objects.filter(name__in=list(value)).values_list('name', flat=True)))):
        raise ValidationError(f'These are no attributes: {", ".join(unknown)}. Create them as attributes first.', code=ATTRIBUTES_CODE)


# a code of its own, since a JSON field replaces the message of any code it knows, as invalid
ATTRIBUTES_CODE = 'invalid_attributes'

SCRYFALL_QUERY_VALIDATOR = LarkGrammarValidator(SCRYFALL_GRAMMAR)

SCRYFALL_QUERY_VALIDATORS: list[Callable[[Any], None]] = [SCRYFALL_QUERY_VALIDATOR, validate_query_regexes]
SCRYFALL_QUERY_HELP = f'''\
Variables supported: {', '.join(VARIABLES_SUPPORTED)}.
Operators supported: =, !=, <, >, <=, >=, :.
You can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)".
You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature".
Card names are only supported if wrapped in double quotes and preceded by an exclamation mark (!) in order to match the exact name, like !"Lightning Bolt".
You can negate any expression by prepending a dash (-), like "-t:creature".
A regular expression must be at most {MAX_REGEX_LENGTH} characters long, and may not repeat a group
that repeats or chooses within itself, since that can take exponential time to match.
More info at: https://scryfall.com/docs/syntax.
'''
