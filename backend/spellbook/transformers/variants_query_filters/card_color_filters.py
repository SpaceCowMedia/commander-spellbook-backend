from .base import QueryValue, VariantFilterCollection, Q, ValidationError
from spellbook.parsers.color_parser import parse_color


def card_color_filter(qv: QueryValue) -> VariantFilterCollection:
    value_is_digit = qv.value.isdigit()
    color = ''
    not_in_color = ''
    if not value_is_digit:
        color = parse_color(qv.value)
        if color is None:
            raise ValidationError(f'Invalid color: {qv.value}')
        elif color == 'C':
            color = ''
        for c in 'WUBRG':
            if c not in color:
                not_in_color += c
    match qv.operator:
        case ':' | '=' if not value_is_digit:
            q = Q(color=color or 'C')
        case '<' if not value_is_digit:
            q = Q(color_count__lt=len(color))
            for c in not_in_color:
                q &= Q(**{f'color_{c.lower()}': False})
        case '<=' if not value_is_digit:
            q = Q(color_count__lte=len(color))
            for c in not_in_color:
                q &= Q(**{f'color_{c.lower()}': False})
        case '>' if not value_is_digit:
            q = Q(color_count__gt=len(color))
            for c in color:
                q &= Q(**{f'color_{c.lower()}': True})
        case '>=' if not value_is_digit:
            q = Q(color_count__gte=len(color))
            for c in color:
                q &= Q(**{f'color_{c.lower()}': True})
        case ':' | '=' if value_is_digit:
            q = Q(color_count=qv.value)
        case '<' if value_is_digit:
            q = Q(color_count__lt=qv.value)
        case '<=' if value_is_digit:
            q = Q(color_count__lte=qv.value)
        case '>' if value_is_digit:
            q = Q(color_count__gt=qv.value)
        case '>=' if value_is_digit:
            q = Q(color_count__gte=qv.value)
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card color search with {"numbers" if value_is_digit else "strings"}.')
    return VariantFilterCollection(cards_filters=(qv.to_query_filter(q),))
