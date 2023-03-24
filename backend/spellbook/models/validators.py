from django.core.validators import RegexValidator, MinLengthValidator

MANA_SYMBOL = r'(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)'
MANA_REGEX = r'^(\{' + MANA_SYMBOL + r'\} *)*$'
MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format.')

DOUBLE_SQUARE_BRACKET_TEXT_REGEX = r'^(?:[^\[]*(?:\[(?!\[)|\[{2}[^\[]+\]{2}|\[{3,}))*[^\[]*$'
DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')

ORACLE_SYMBOL = r'(?:[0-9WUBRGCPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)'
SYMBOLS_TEXT_REGEX = r'^(?:[^\{]*\{' + ORACLE_SYMBOL + r'\})*[^\{]*$'
SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')

TEXT_VALIDATORS = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR]

IDENTITY_REGEX = r'^(?:W?U?B?R?G?|C)$'
IDENTITY_VALIDATORS = [RegexValidator(regex=IDENTITY_REGEX, message='Can be any combination of one or more letters in [W,U,B,R,G], in order, otherwise C for colorless.'), MinLengthValidator(1)]

# Scryfall query syntax: https://scryfall.com/docs/syntax
COMPARISON_OPERATORS = r'(?::|[<>]=?|!=|=)'
NUMERIC_VARIABLE = r'(?:mv|manavalue|power|pow|toughness|tou|pt|powtou|loyalty|loy)'
SCRYFALL_QUERY_ATOM = r'(?:-?(?:' + \
    r'(?:(?:c|color|id|identity|produces)' + COMPARISON_OPERATORS + r'|(?:has|t|type|keyword|is):)(?:[^\s:<>!="]+|"[^"]+")|' + \
    r'(?:m|mana|devotion)' + COMPARISON_OPERATORS + r'(?:\{' + MANA_SYMBOL + r'\})+|' + \
    NUMERIC_VARIABLE + COMPARISON_OPERATORS + r'(?:\d+|' + NUMERIC_VARIABLE + r')' + \
    r'))'
SCRYFALL_EXPRESSION = r'(?:' + SCRYFALL_QUERY_ATOM + r'(?: (?:and |or )?' + SCRYFALL_QUERY_ATOM + r')*)'
SCRYFALL_EXPRESSION_BRACKETS = r'(?:\(' + SCRYFALL_EXPRESSION + r'\)|' + SCRYFALL_EXPRESSION + r')'
SCRYFALL_QUERY_REGEX = r'^(?:' + SCRYFALL_EXPRESSION_BRACKETS + r'(?: (?:and |or )?' + SCRYFALL_EXPRESSION_BRACKETS + r')*)$'
SCRYFALL_QUERY_VALIDATOR = RegexValidator(regex=SCRYFALL_QUERY_REGEX, message='Invalid Scryfall query syntax.')
SCRYFALL_QUERY_HELP = 'Variables supported: manavalue, mv, power, pow, toughness, tou, powtou, pt, loyalty, loy, color, c, identity, id, has, type, t, keyword, is, mana, m, devotion, produces. Operators supported: =, !=, <, >, <=, >=, :. You can compose a "and"/"or" expression made of "and"/"or" expressions, like "(c:W or c:U) and (t:creature or t:artifact)". You can also omit parentheses when not necessary, like "(c:W or c:U) t:creature". More info at: https://scryfall.com/docs/syntax.'
