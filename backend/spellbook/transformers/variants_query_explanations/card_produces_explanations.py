from spellbook.models import Card
from spellbook.parsers.color_parser import parse_color
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, about, color_names


def card_produces_explanation(qv: QueryValue) -> Explanation:
    parsed_color = parse_color(qv.value)
    if parsed_color is None:
        raise ValidationError(f'Invalid color: {qv.value}')
    colors = color_names(parsed_color)
    match qv.operator:
        case ':' | '>=':
            return about(qv, USE, Card, f'{ENTITY} producing {colors} mana')
        case '=':
            return about(qv, USE, Card, f'{ENTITY} producing exactly {colors} mana')
        case '<=':
            return about(qv, USE, Card, f'{ENTITY} producing no mana outside {colors}')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card produced mana search.')
