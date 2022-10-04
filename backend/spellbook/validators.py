from django.core.validators import RegexValidator

MANA_SYMBOL = r'(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)'
MANA_REGEX = r'^(\{' + MANA_SYMBOL + r'\} *)*$'
MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format.')

DOUBLE_SQUARE_BRACKET_TEXT_REGEX = r'^(?:[^\[]*(?:\[(?!\[)|\[{2}[^\[]+\]{2}|\[{3,}))*[^\[]*$'
DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

ORACLE_SYMBOL = r'(?:[0-9WUBRGCPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)'
SYMBOLS_TEXT_REGEX = r'^(?:[^\{]*\{' + ORACLE_SYMBOL + r'\})*[^\{]*$'
SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

TEXT_VALIDATORS = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR]

IDENTITY_REGEX = r'^W?U?B?R?G?$'
IDENTITY_VALIDATOR = RegexValidator(regex=IDENTITY_REGEX, message='Can be any combination of zero or more letters in [W,U,B,R,G], in order.')

# Scryfall query syntax: https://scryfall.com/docs/syntax
COMPARISON_OPERATORS = r'(?::|[<>]=?|!=|=)'
NUMERIC_VARIABLE = r'(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)'
SCRYFALL_QUERY_ATOM = r'(?:-?(?:' + \
    r'(?:(?:c|color|id|identity)' + COMPARISON_OPERATORS + r'|(?:has|t|type|keyword|is):)(?:[^\s:<>!="]+|"[^"]+")|' + \
    r'(?:m|mana|devotion|produces)' + COMPARISON_OPERATORS + r'(?:\{' + MANA_SYMBOL + r'\})+|' + \
    NUMERIC_VARIABLE + COMPARISON_OPERATORS + r'(?:\d+|' + NUMERIC_VARIABLE + r')' + \
    r'))'
SCRYFALL_EXPRESSION = r'(?:' + SCRYFALL_QUERY_ATOM + r'(?: (?:and |or )?' + SCRYFALL_QUERY_ATOM + r')*)'
SCRYFALL_EXPRESSION_BRACKETS = r'(?:\(' + SCRYFALL_EXPRESSION + r'\)|' + SCRYFALL_EXPRESSION + r')'
SCRYFALL_QUERY_REGEX = r'^(?:' + SCRYFALL_EXPRESSION_BRACKETS + r'(?: (?:and |or )?' + SCRYFALL_EXPRESSION_BRACKETS + r')*)$'
SCRYFALL_QUERY_VALIDATOR = RegexValidator(regex=SCRYFALL_QUERY_REGEX, message='Invalid Scryfall query syntax.')
SCRYFALL_QUERY_HELP = 'Variables supported: mv, manavalue, power, pow, toughness, tou, pt, powtou, loyalty, loyalty, c, color, id, identity, has, t, type, keyword, is, m, mana, devotion, produces. Operators supported: =, !=, <, >, <=, >=, :. You can compose a "and" expression made of "or" expression, like "(c:W or c:U) and (t:creature or t:artifact)". You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature". More info at https://scryfall.com/docs/syntax.'
