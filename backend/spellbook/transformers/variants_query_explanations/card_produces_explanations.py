from spellbook.models import Card
from spellbook.parsers.color_parser import parse_produced_mana
from .base import QueryValue, ENTITY, Explanation, USE, ValidationError, COLOR_NAMES, about, color_names, count, join


def card_produces_explanation(qv: QueryValue) -> Explanation:
    produced = parse_produced_mana(qv.value, qv.operator)
    if produced is None:
        raise ValidationError(f'Invalid color: {qv.value}')
    operator, target = produced
    if isinstance(target, int):
        return about(qv, USE, Card, f'{ENTITY} producing {count(operator, str(target), 'kind of mana', 'kinds of mana')}')
    colors = color_names(target)
    alternatives = join(tuple(COLOR_NAMES[kind] for kind in target), conjunction=False)
    match operator:
        case ':' | '>=':
            return about(qv, USE, Card, f'{ENTITY} producing {colors} mana')
        case '=':
            return about(qv, USE, Card, f'{ENTITY} producing exactly {colors} mana')
        case '<=':
            return about(qv, USE, Card, f'{ENTITY} producing only {alternatives} mana')
        case '<':
            return about(qv, USE, Card, f'{ENTITY} producing only {alternatives} mana, but not all of them')
        case '>':
            return about(qv, USE, Card, f'{ENTITY} producing {colors} mana and more')
        case _:
            raise ValidationError(f'Operator {qv.operator} is not supported for card produced mana search.')
