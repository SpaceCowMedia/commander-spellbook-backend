from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import F, Q
from django.db.models.expressions import Combinable
from spellbook.models import oracle_tag_condition
from spellbook.parsers.color_parser import parse_color
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


def colors_of(value: ScryfallValue) -> set[str]:
    '''The colours a query names, where a zero and the word colourless both name none of them.'''
    if value.value in ('0', ''):
        return set()
    parsed = parse_color(value.value)
    if parsed is None:
        raise ValidationError(f'{value.value} does not name any colour.')
    return set(parsed) - {'C'}


def produces_filter(value: ScryfallValue) -> Q:
    return Q(*(Q(produced_mana__icontains=f'"{color}"') for color in colors_of(value)))


def color_filter(value: ScryfallValue, field: str) -> Q:
    '''A colour set compared to the queried one, over the generated per colour columns.'''
    colors = colors_of(value)
    count = f'{field}_count'
    has = {color: Q(**{f'{field}_{color.lower()}': True}) for color in 'WUBRG'}
    inside = Q(*(~has[color] for color in 'WUBRG' if color not in colors))
    holds = Q(*(has[color] for color in colors))
    match value.operator:
        case ':' | '>=':
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
