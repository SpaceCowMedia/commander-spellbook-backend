from django.core.validators import RegexValidator
from ..regexs import RESERVED_CHARACTERS_REGEX, URL_REGEX, FIRST_CAPITAL_LETTER_REGEX, NO_TRAILING_PUNCTUATION_REGEX, MANA_REGEX, DOUBLE_SQUARE_BRACKET_TEXT_REGEX, SYMBOLS_TEXT_REGEX, ORDINARY_CHARACTERS_REGEX
from ..parsers.scryfall_query_grammar import SCRYFALL_GRAMMAR, VARIABLES_SUPPORTED
from ..parsers.lark_validator import LarkGrammarValidator

NOT_URL_VALIDATOR = RegexValidator(regex=URL_REGEX, inverse_match=True, message='URLs are not allowed.')

FIRST_CAPITAL_LETTER_VALIDATOR = RegexValidator(regex=FIRST_CAPITAL_LETTER_REGEX, message='Must start with a capital letter.')

NO_TRAILING_PUNCTUATION_VALIDATOR = RegexValidator(regex=NO_TRAILING_PUNCTUATION_REGEX, message='Must not end with punctuation.')

MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format, and must start with mana symbols, but can contain normal text later.')

DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

ORDINARY_CHARACTERS_VALIDATOR = RegexValidator(regex=ORDINARY_CHARACTERS_REGEX, message='Only ordinary characters are allowed.')

NO_RESERVED_CHARACTERS_VALIDATOR = RegexValidator(regex=RESERVED_CHARACTERS_REGEX, inverse_match=True, message=f'Reserved characters are not allowed. Examples of reserved characters: $, |.')

TEXT_VALIDATORS = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR, ORDINARY_CHARACTERS_VALIDATOR]
NAME_VALIDATORS = [FIRST_CAPITAL_LETTER_VALIDATOR, NO_TRAILING_PUNCTUATION_VALIDATOR, NOT_URL_VALIDATOR, NO_RESERVED_CHARACTERS_VALIDATOR, *TEXT_VALIDATORS]

SCRYFALL_QUERY_VALIDATOR = LarkGrammarValidator(SCRYFALL_GRAMMAR)
SCRYFALL_QUERY_HELP = f'''\
Variables supported: {', '.join(VARIABLES_SUPPORTED)}.
Operators supported: =, !=, <, >, <=, >=, :.
You can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)".
You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature".
Card names are only supported if wrapped in double quotes and preceded by an exclamation mark (!) in order to match the exact name, like !"Lightning Bolt".
You can negate any expression by prepending a dash (-), like "-t:creature".
More info at: https://scryfall.com/docs/syntax.
'''
