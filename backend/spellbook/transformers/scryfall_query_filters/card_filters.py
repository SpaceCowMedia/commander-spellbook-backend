from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F, Q
from django.db.models.expressions import Combinable
from spellbook.models import oracle_tag_condition
from spellbook.models.utils import PRODUCED_MANA_KINDS
from spellbook.parsers.color_parser import parse_colors, parse_produced_mana
from spellbook.parsers.safe_regex import exclude_newline, expand_card_name, validate_safe_regex
from ..query_parsing import compare
from .base import ScryfallValue

NUMERIC_CHARACTERISTICS: dict[str, str | Combinable] = {
    'mv': 'mana_value',
    'manavalue': 'mana_value',
    'power': 'power_value',
    'pow': 'power_value',
    'toughness': 'toughness_value',
    'tou': 'toughness_value',
    'loyalty': 'loyalty_value',
    'loy': 'loyalty_value',
    'pt': F('power_value') + F('toughness_value'),
    'powtou': F('power_value') + F('toughness_value'),
}

PERMANENT_TYPES = ('Artifact', 'Creature', 'Enchantment', 'Land', 'Planeswalker', 'Battle')

DOUBLE_FACED_LAYOUTS = ('transform', 'modal_dfc', 'double_faced_token', 'reversible_card')


def name_filter(name: str) -> Q:
    return Q(name__iexact=name) | Q(name_unaccented__iexact=name) | Q(name__istartswith=f'{name} //')


def type_filter(value: ScryfallValue) -> Q:
    return Q(type_line__icontains=value.value)


def line_by_line(pattern: str) -> str:
    '''The pattern as the database will read it, matching a line of the text rather than the whole of it.

    PostgreSQL spells that (?n). Python, which is what SQLite runs a regular expression through, has no
    such flag: (?m) anchors ^ and $ to a line the same way and its dot already stops at a newline, which
    leaves only a negated class to tell.'''
    if connection.vendor == 'postgresql':
        return f'(?n){pattern}'
    return f'(?m){exclude_newline(pattern)}'


def oracle_filter(value: ScryfallValue) -> Q:
    '''The oracle text, where a tilde stands for the card's own name the way Scryfall writes it.

    A regular expression is read line by line, the way Scryfall reads one: an oracle text is a
    handful of lines, and an anchored pattern is written to match one of them, not the whole card.'''
    if value.regex:
        # checked here as well as where the query is saved, so that nothing reaches the database with a
        # pattern that could take exponential time to match
        pattern = expand_card_name(value.value)
        validate_safe_regex(pattern)
        return Q(oracle_text__iregex=line_by_line(pattern))
    if '~' in value.value:
        head, _, tail = value.value.partition('~')
        return Q(oracle_text__icontains=head) & Q(oracle_text__icontains=tail)
    return Q(oracle_text__icontains=value.value)


def keyword_filter(value: ScryfallValue) -> Q:
    return Q(keywords__icontains=f'"{value.value}"')


def produced_mana_condition(operator: str, target: str | int) -> Q:
    '''The kinds of mana a card makes compared to the ones named, as one set to another, or their number
    compared to a count.

    Only a card making some mana is within a set, the way Scryfall reads it, whereas one making none
    still differs from it.'''
    if isinstance(target, int):
        return compare('produced_mana_count', operator, target)
    target_kinds = set(target)
    holds = [kinds for kinds in PRODUCED_MANA_KINDS if target_kinds <= set(kinds)]
    inside = [kinds for kinds in PRODUCED_MANA_KINDS if set(kinds) <= target_kinds and kinds]
    match operator:
        case ':' | '>=':
            return Q(produced_mana__in=holds)
        case '=':
            return Q(produced_mana=target)
        case '!=':
            return ~Q(produced_mana=target)
        case '<=':
            return Q(produced_mana__in=inside)
        case '<':
            return Q(produced_mana__in=[kinds for kinds in inside if kinds != target])
        case '>':
            return Q(produced_mana__in=[kinds for kinds in holds if kinds != target])
        case _:
            raise ValidationError(f'Operator {operator} is not supported for produced mana search.')


def produces_filter(value: ScryfallValue) -> Q:
    produced = parse_produced_mana(value.value, value.operator)
    if produced is None:
        raise ValidationError(f'{value.value} does not name any colour.')
    return produced_mana_condition(*produced)


def color_filter(value: ScryfallValue, field: str) -> Q:
    '''A colour set compared to the queried one, over the generated per colour columns.

    A colon asks a card's colours to include the queried ones but its identity to fit within them, the
    way Scryfall reads each; asking either for no colours at all asks for colourless.'''
    parsed = parse_colors(value.value, value.operator)
    if parsed is None:
        raise ValidationError(f'{value.value} does not name any colour.')
    operator, colors = parsed
    count = f'{field}_count'
    if isinstance(colors, int):
        return compare(count, operator, colors)
    if operator == ':':
        operator = '<=' if field == 'identity' or not colors else '>='
    has = {color: Q(**{f'{field}__contains': color}) for color in 'WUBRG'}
    inside = Q(*(~has[color] for color in 'WUBRG' if color not in colors))
    holds = Q(*(has[color] for color in colors))
    match operator:
        case '>=':
            return holds
        case '=':
            return holds & inside
        case '<=':
            return inside
        case '<':
            return inside & Q(**{f'{count}__lt': len(colors)})
        case '>':
            return holds & Q(**{f'{count}__gt': len(colors)})
        case '!=':
            return ~(holds & inside)
        case _:
            raise value.unsupported()


def is_filter(value: ScryfallValue) -> Q:
    '''The shorthands a query asks a card by, each spelled out over the columns that decide it.'''
    match value.value.lower():
        case 'permanent':
            return Q(*(Q(type_line__icontains=card_type) for card_type in PERMANENT_TYPES), _connector=Q.OR)
        case 'spell':
            return ~Q(type_line__icontains='Land') & ~Q(type_line__icontains='Token')
        case 'dfc' | 'doublefaced' | 'double_faced':
            return Q(layout__in=DOUBLE_FACED_LAYOUTS)
        case 'tdfc' | 'transform':
            return Q(layout='transform')
        case 'mdfc':
            return Q(layout='modal_dfc')
        case 'flip':
            return Q(layout='flip')
        case 'split':
            return Q(layout='split')
        case 'adventure':
            return Q(layout='adventure')
        case 'hybrid':
            return Q(mana_cost__regex=r'\{[WUBRG2]/[WUBRG]\}')
        case 'phyrexian':
            return Q(mana_cost__icontains='/P}')
        case 'commander':
            return Q(legal_commander=True) & Q(
                Q(type_line__icontains='Legendary Creature'),
                Q(type_line__icontains='Background'),
                Q(oracle_text__icontains='can be your commander'),
                _connector=Q.OR,
            )
        case 'reserved':
            return Q(reserved=True)
        case 'gamechanger' | 'game_changer':
            return Q(game_changer=True)
        case 'spoiler' | 'preview':
            return Q(spoiler=True)
        case 'reprint':
            return Q(reprinted=True)
        case 'vanilla':
            return Q(oracle_text='')
        case unknown:
            raise ValidationError(f'The value {unknown} is not supported for an is: search.')


def oracle_tag_filter(value: ScryfallValue) -> Q:
    '''A tag the Scryfall taggers put on the card, matched against the joins the sync already rolled up.'''
    return oracle_tag_condition(value.value)


def oracle_id_filter(value: ScryfallValue) -> Q:
    return Q(oracle_id=value.value)


def numeric_field_filter(value: ScryfallValue) -> Q:
    '''A characteristic compared to a number, or to whichever other characteristic the query names.'''
    right = NUMERIC_CHARACTERISTICS[value.value] if value.value in NUMERIC_CHARACTERISTICS else int(value.value)
    return compare(NUMERIC_CHARACTERISTICS[value.key], value.operator, right)
