from .base import QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.parsers.color_parser import parse_color


def identity_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    identity = ''
    not_in_identity = ''
    if not value_is_digit:
        identity = parse_color(qv.value)
        if identity is None:
            raise ValidationError(f'Invalid color identity: {qv.value}')
        elif identity == 'C':
            identity = ''
        for color in 'WUBRG':
            if color not in identity:
                not_in_identity += color
    match qv.operator:
        case '=' if not value_is_digit:
            q = Q(identity=identity or 'C')
        case '<' if not value_is_digit:
            q = Q(identity_count__lt=len(identity))
            for color in not_in_identity:
                q &= Q(**{f'identity_{color.lower()}': False})
        case ':' | '<=' if not value_is_digit:
            q = Q(identity_count__lte=len(identity))
            for color in not_in_identity:
                q &= Q(**{f'identity_{color.lower()}': False})
        case '>' if not value_is_digit:
            q = Q(identity_count__gt=len(identity))
            for color in identity:
                q &= Q(**{f'identity_{color.lower()}': True})
        case '>=' if not value_is_digit:
            q = Q(identity_count__gte=len(identity))
            for color in identity:
                q &= Q(**{f'identity_{color.lower()}': True})
        case ':' | '=' if value_is_digit:
            q = Q(identity_count=qv.value)
        case '<' if value_is_digit:
            q = Q(identity_count__lt=qv.value)
        case '<=' if value_is_digit:
            q = Q(identity_count__lte=qv.value)
        case '>' if value_is_digit:
            q = Q(identity_count__gt=qv.value)
        case '>=' if value_is_digit:
            q = Q(identity_count__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for identity search with {"numbers" if value_is_digit else "strings"}.')
    return VariantFilterCollection(variants_filters=(qv.to_query_filter(q),))
