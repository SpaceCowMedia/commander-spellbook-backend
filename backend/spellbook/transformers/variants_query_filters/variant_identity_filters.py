from .base import QueryValue, QueryFilter, VariantFilterCollection, Q, ValidationError
from spellbook.parsers.color_parser import parse_identity


def identity_filter(identity_value: QueryValue) -> VariantFilterCollection:
    value_is_digit = identity_value.value.isdigit()
    identity = ''
    not_in_identity = ''
    if not value_is_digit:
        identity = parse_identity(identity_value.value)
        if identity is None:
            raise ValidationError(f'Invalid color identity: {identity_value.value}')
        elif identity == 'C':
            identity = ''
        for color in 'WUBRG':
            if color not in identity:
                not_in_identity += color
    match identity_value.operator:
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
        case '=' | ':' if value_is_digit:
            q = Q(identity_count=identity_value.value)
        case '<' if value_is_digit:
            q = Q(identity_count__lt=identity_value.value)
        case '<=' if value_is_digit:
            q = Q(identity_count__lte=identity_value.value)
        case '>' if value_is_digit:
            q = Q(identity_count__gt=identity_value.value)
        case '>=' if value_is_digit:
            q = Q(identity_count__gte=identity_value.value)
        case _:
            raise ValidationError(f'Operator {identity_value.operator} is not supported for identity search with {"numbers" if value_is_digit else "strings"}.')
    return VariantFilterCollection(
        variants_filters=(
            QueryFilter(
                q=q,
                negated=identity_value.is_negated(),
            ),
        ),
    )
