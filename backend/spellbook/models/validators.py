import re
from typing import Any, Callable
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible
from ..regexs import RESERVED_CHARACTERS_REGEX, URL_REGEX, FIRST_CAPITAL_LETTER_REGEX, NO_TRAILING_PUNCTUATION_REGEX, MANA_REGEX, DOUBLE_SQUARE_BRACKET_TEXT_REGEX, DOUBLE_CURLY_BRACKET_TEXT_REGEX, SYMBOLS_TEXT_REGEX, ORDINARY_CHARACTERS_REGEX, LINE_REFERENCE_KEY_REGEX, LINE_REFERENCE_REGEX
from ..parsers.scryfall_query_grammar import SCRYFALL_GRAMMAR, VARIABLES_SUPPORTED
from ..parsers.lark_validator import LarkGrammarValidator
from ..parsers.safe_regex import MAX_REGEX_LENGTH, validate_query_regexes

NOT_URL_VALIDATOR = RegexValidator(regex=URL_REGEX, inverse_match=True, message='URLs are not allowed.')

FIRST_CAPITAL_LETTER_VALIDATOR = RegexValidator(regex=FIRST_CAPITAL_LETTER_REGEX, message='Must start with a capital letter.')

NO_TRAILING_PUNCTUATION_VALIDATOR = RegexValidator(regex=NO_TRAILING_PUNCTUATION_REGEX, message='Must not end with punctuation.')

MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.')

DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

DOUBLE_CURLY_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_CURLY_BRACKET_TEXT_REGEX, message='Unpaired double curly brackets are not allowed.')

SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

ORDINARY_CHARACTERS_VALIDATOR = RegexValidator(regex=ORDINARY_CHARACTERS_REGEX, message='Only ordinary characters are allowed.')

NO_RESERVED_CHARACTERS_VALIDATOR = RegexValidator(regex=RESERVED_CHARACTERS_REGEX, inverse_match=True, message='Reserved characters are not allowed. Examples of reserved characters: $, |.')

NOT_LINE_REFERENCE_VALIDATOR = RegexValidator(regex=f'^{LINE_REFERENCE_KEY_REGEX}$', inverse_match=True, message='Must not be a line reference, like 3, +4 or -3.')

LINE_REFERENCE_PATTERN = re.compile(LINE_REFERENCE_REGEX)


def referenced_line(reference: re.Match[str], line: int) -> int:
    '''The line of its text a line reference written on the given line points at.'''
    number = int(reference['number'])
    match reference['sign']:
        case '+':
            return line + number
        case '-':
            return line - number
        case _:
            return number


@deconstructible
class LineReferenceValidator:
    '''Rejects a line reference pointing at a line the text it is written in does not have.'''
    message = '%(reference)s on line %(line)s points at a line the text does not have.'
    code = 'invalid'

    def __init__(self, message: str | None = None, code: str | None = None):
        if message is not None:
            self.message = message
        if code is not None:
            self.code = code

    def __call__(self, value: str) -> None:
        lines = value.split('\n')
        for position, line in enumerate(lines, start=1):
            for reference in LINE_REFERENCE_PATTERN.finditer(line):
                if not 1 <= referenced_line(reference, position) <= len(lines):
                    raise ValidationError(self.message, code=self.code, params={'reference': reference[0], 'line': position})

    def __eq__(self, other: object) -> bool:
        return isinstance(other, LineReferenceValidator) and self.message == other.message and self.code == other.code


LINE_REFERENCE_VALIDATOR = LineReferenceValidator()

TEXT_VALIDATORS: list[Callable[[Any], None]] = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, DOUBLE_CURLY_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR, ORDINARY_CHARACTERS_VALIDATOR, LINE_REFERENCE_VALIDATOR]
NAME_VALIDATORS: list[Callable[[Any], None]] = [FIRST_CAPITAL_LETTER_VALIDATOR, NO_TRAILING_PUNCTUATION_VALIDATOR, NOT_URL_VALIDATOR, NO_RESERVED_CHARACTERS_VALIDATOR, *TEXT_VALIDATORS]
FEATURE_NAME_VALIDATORS: list[Callable[[Any], None]] = [*NAME_VALIDATORS, NOT_LINE_REFERENCE_VALIDATOR]

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
