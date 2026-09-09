from ..query_parsing import compare
from .base import QueryValue, VariantQuery, Q, ValidationError
from spellbook.parsers.color_parser import parse_color


def identity_filter(qv: QueryValue) -> VariantQuery:
    value_is_digit = qv.is_numeric()
    identity = ''
    not_in_identity = ''
    if not value_is_digit:
        parsed_identity = parse_color(qv.value)
        if parsed_identity is None:
            raise ValidationError(f'Invalid color identity: {qv.value}')
        identity = '' if parsed_identity == 'C' else parsed_identity
        for color in 'WUBRG':
            if color not in identity:
                not_in_identity += color
    match qv.operator:
        case '=' if not value_is_digit:
            q = Q(identity=identity or 'C')
        case ':' | '<' | '<=' if not value_is_digit:
            # a bare colon asks for an identity that fits inside the queried one, which is what <= asks
            q = compare('identity_count', '<=' if qv.operator == ':' else qv.operator, len(identity))
            for color in not_in_identity:
                q &= Q(**{f'identity_{color.lower()}': False})
        case '>' | '>=' if not value_is_digit:
            q = compare('identity_count', qv.operator, len(identity))
            for color in identity:
                q &= Q(**{f'identity_{color.lower()}': True})
        case _ if value_is_digit:
            q = compare('identity_count', qv.operator, int(qv.value))
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for identity search with {'numbers' if value_is_digit else 'strings'}.')
    return qv.to_filter(q)
