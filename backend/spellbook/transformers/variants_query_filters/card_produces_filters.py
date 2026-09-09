from spellbook.models import Card
from spellbook.parsers.color_parser import parse_color
from .base import QueryValue, VariantQuery, Q, ValidationError


def produced_colors(qv: QueryValue) -> set[str]:
    parsed_color = parse_color(qv.value)
    if parsed_color is None:
        raise ValidationError(f'Invalid color: {qv.value}')
    return set(parsed_color) - {'C'}


def card_produces_filter(qv: QueryValue) -> VariantQuery:
    '''The mana a card can produce, compared to the queried colors as one set to another.

    Only the colors are compared: the column records which of them a card makes, not how much, so
    counting them the way a color search counts colors has nothing to count.'''
    colors = produced_colors(qv)
    produces = {color: Q(produced_mana__icontains=f'"{color}"') for color in 'WUBRG'}
    holds = Q(*(produces[color] for color in colors))
    inside = Q(*(~produces[color] for color in 'WUBRG' if color not in colors))
    match qv.operator:
        case ':' | '>=':
            q = holds
        case '=':
            q = holds & inside
        case '<=':
            q = inside
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card produced mana search.')
    return qv.to_filter(q, Card)
