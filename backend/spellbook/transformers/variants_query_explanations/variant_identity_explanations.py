from spellbook.parsers.color_parser import parse_color
from .base import QueryValue, Explanation, Predicate, HAVE, ValidationError, color_names, count


def identity_explanation(qv: QueryValue) -> Explanation:
    value_is_digit = qv.is_numeric()
    colors = ''
    colorless = False
    if not value_is_digit:
        parsed_identity = parse_color(qv.value)
        if parsed_identity is None:
            raise ValidationError(f'Invalid color identity: {qv.value}')
        colorless = parsed_identity == 'C'
        colors = color_names(parsed_identity)
    match qv.operator:
        case '=' if not value_is_digit:
            complement = 'a colorless color identity' if colorless else f'a color identity of exactly {colors}'
        case '<' if not value_is_digit:
            complement = f'a color identity within, but not equal to, {colors}'
        case ':' | '<=' if not value_is_digit:
            complement = 'a colorless color identity' if colorless else f'a color identity within {colors}'
        case '>' if not value_is_digit:
            complement = f'a color identity that includes {colors} and more'
        case '>=' if not value_is_digit:
            complement = f'a color identity that includes {colors}'
        case ':' | '=' | '<' | '<=' | '>' | '>=' if value_is_digit:
            complement = f'{count(qv.operator, qv.value, 'color', 'colors')} in their color identity'
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for identity search with {'numbers' if value_is_digit else 'strings'}.')
    return Predicate(HAVE, complement)
