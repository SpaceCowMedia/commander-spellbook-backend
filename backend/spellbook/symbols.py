from django.core.validators import RegexValidator


MANA_REGEX = r'^(\{(?:[0-9WUBRGCPXYZS∞]|[1-9][0-9]{1,2}|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)\} *)*$'
MANA_VALIDATOR = RegexValidator(regex=MANA_REGEX, message='Mana needed must be in the {1}{W}{U}{B}{R}{G}{B/P}... format.')
DOUBLE_SQUARE_BRACKET_TEXT_REGEX = r'^(?:[^\[]*(?:\[(?!\[)|\[{2}[^\[]+\]{2}|\[{3,}))*[^\[]*$'
DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR = RegexValidator(regex=DOUBLE_SQUARE_BRACKET_TEXT_REGEX, message='Unpaired double square brackets are not allowed.')
SYMBOLS_TEXT_REGEX = r'^(?:[^\{]*\{(?:[0-9WUBRGCPXYZSTQEA½∞]|PW|CHAOS|TK|[1-9][0-9]{1,2}|H[WUBRG]|(?:2\/[WUBRG]|W\/U|W\/B|B\/R|B\/G|U\/B|U\/R|R\/G|R\/W|G\/W|G\/U)(?:\/P)?)\})*[^\{]*$'
SYMBOLS_TEXT_VALIDATOR = RegexValidator(regex=SYMBOLS_TEXT_REGEX, message='Symbols must be in the {1}{W}{U}{B}{R}{G}{B/P}{A}{E}{T}{Q}... format.')
TEXT_VALIDATORS = [DOUBLE_SQUARE_BRACKET_TEXT_VALIDATOR, SYMBOLS_TEXT_VALIDATOR]
