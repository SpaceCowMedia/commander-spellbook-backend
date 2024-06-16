import re
from django.db.models import Q, QuerySet
from collections import defaultdict
from typing import Callable
from dataclasses import dataclass
from spellbook.models import Variant
from website.models import WebsiteProperty, FEATURED_SET_CODES
from common.query import smart_apply_filters, Filter
from .color_parser import parse_identity


@dataclass
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str


def card_search(card_value: QueryValue) -> list[Q]:
    value_is_digit = card_value.value.isdigit()
    match card_value.operator:
        case ':' if not value_is_digit:
            card_query = Q(uses__name__icontains=card_value.value) \
                | Q(uses__name_unaccented__icontains=card_value.value) \
                | Q(uses__name_unaccented_simplified__icontains=card_value.value) \
                | Q(uses__name_unaccented_simplified_with_spaces__icontains=card_value.value)
        case '=' if not value_is_digit:
            card_query = Q(uses__name__iexact=card_value.value) \
                | Q(uses__name_unaccented__iexact=card_value.value) \
                | Q(uses__name_unaccented_simplified__iexact=card_value.value) \
                | Q(uses__name_unaccented_simplified_with_spaces__iexact=card_value.value)
        case '<' if value_is_digit:
            card_query = Q(cards_count__lt=card_value.value)
        case '>' if value_is_digit:
            card_query = Q(cards_count__gt=card_value.value)
        case '<=' if value_is_digit:
            card_query = Q(cards_count__lte=card_value.value)
        case '>=' if value_is_digit:
            card_query = Q(cards_count__gte=card_value.value)
        case ':' | '=' if value_is_digit:
            card_query = Q(cards_count=card_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_value.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
    return [card_query]


def card_type_search(card_type_value: QueryValue) -> list[Q]:
    match card_type_value.operator:
        case ':':
            card_type_query = Q(uses__type_line__icontains=card_type_value.value)
        case '=':
            card_type_query = Q(uses__type_line__iexact=card_type_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_type_value.operator} is not supported for card type search.')
    return [card_type_query]


def card_oracle_search(card_oracle_value: QueryValue) -> list[Q]:
    match card_oracle_value.operator:
        case ':':
            card_oracle_query = Q(uses__oracle_text__icontains=card_oracle_value.value)
        case '=':
            card_oracle_query = Q(uses__oracle_text__iexact=card_oracle_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_oracle_value.operator} is not supported for card oracle search.')
    return [card_oracle_query]


def card_keyword_search(card_keyword_value: QueryValue) -> list[Q]:
    match card_keyword_value.operator:
        case ':':
            card_keyword_query = Q(uses__keywords__icontains=card_keyword_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_keyword_value.operator} is not supported for card keyword search.')
    return [card_keyword_query]


def card_mana_value_search(card_mana_value_value: QueryValue) -> list[Q]:
    value_is_digit = card_mana_value_value.value.isdigit()
    match card_mana_value_value.operator:
        case ':' | '=' if value_is_digit:
            card_mana_value_query = Q(uses__mana_value=card_mana_value_value.value)
        case '<' if value_is_digit:
            card_mana_value_query = Q(uses__mana_value__lt=card_mana_value_value.value)
        case '<=' if value_is_digit:
            card_mana_value_query = Q(uses__mana_value__lte=card_mana_value_value.value)
        case '>' if value_is_digit:
            card_mana_value_query = Q(uses__mana_value__gt=card_mana_value_value.value)
        case '>=' if value_is_digit:
            card_mana_value_query = Q(uses__mana_value__gte=card_mana_value_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_mana_value_value.operator} is not supported for card mana value search with {"numbers" if value_is_digit else "strings"}.')
    return [card_mana_value_query]


def identity_search(identity_value: QueryValue) -> list[Q]:
    value_is_digit = identity_value.value.isdigit()
    identity = ''
    not_in_identity = ''
    if not value_is_digit:
        identity = parse_identity(identity_value.value)
        if identity is None:
            raise NotSupportedError(f'Invalid color identity: {identity_value.value}')
        elif identity == 'C':
            identity = ''
        for color in 'WUBRG':
            if color not in identity:
                not_in_identity += color
    match identity_value.operator:
        case '=' if not value_is_digit:
            identity_queries = [Q(identity=identity or 'C')]
        case '<' if not value_is_digit:
            identity_queries = [Q(identity_count__lt=len(identity))]
            for color in not_in_identity:
                identity_queries.append(~Q(identity__contains=color))
        case ':' | '<=' if not value_is_digit:
            identity_queries = [Q(identity_count__lte=len(identity))]
            for color in not_in_identity:
                identity_queries.append(~Q(identity__contains=color))
        case '>' if not value_is_digit:
            identity_queries = [Q(identity_count__gt=len(identity))]
            for color in identity:
                identity_queries.append(Q(identity__contains=color))
        case '>=' if not value_is_digit:
            identity_queries = [Q(identity_count__gte=len(identity))]
            for color in identity:
                identity_queries.append(Q(identity__contains=color))
        case '=' | ':' if value_is_digit:
            identity_queries = [Q(identity_count=identity_value.value)]
        case '<' if value_is_digit:
            identity_queries = [Q(identity_count__lt=identity_value.value)]
        case '<=' if value_is_digit:
            identity_queries = [Q(identity_count__lte=identity_value.value)]
        case '>' if value_is_digit:
            identity_queries = [Q(identity_count__gt=identity_value.value)]
        case '>=' if value_is_digit:
            identity_queries = [Q(identity_count__gte=identity_value.value)]
        case _:
            raise NotSupportedError(f'Operator {identity_value.operator} is not supported for identity search with {"numbers" if value_is_digit else "strings"}.')
    return identity_queries


def prerequisites_search(prerequisites_value: QueryValue) -> list[Q]:
    value_is_digit = prerequisites_value.value.isdigit()
    match prerequisites_value.operator:
        case ':' if not value_is_digit:
            prerequisites_query = Q(other_prerequisites__icontains=prerequisites_value.value)
        case '=' if not value_is_digit:
            prerequisites_query = Q(other_prerequisites__iexact=prerequisites_value.value)
        case '<' if value_is_digit:
            prerequisites_query = Q(other_prerequisites_line_count__lt=prerequisites_value.value)
        case '<=' if value_is_digit:
            prerequisites_query = Q(other_prerequisites_line_count__lte=prerequisites_value.value)
        case '>' if value_is_digit:
            prerequisites_query = Q(other_prerequisites_line_count__gt=prerequisites_value.value)
        case '>=' if value_is_digit:
            prerequisites_query = Q(other_prerequisites_line_count__gte=prerequisites_value.value)
        case ':' | '=' if value_is_digit:
            prerequisites_query = Q(other_prerequisites_line_count=prerequisites_value.value)
        case _:
            raise NotSupportedError(f'Operator {prerequisites_value.operator} is not supported for prerequisites search.')
    return [prerequisites_query, Q(status=Variant.Status.OK)]


def description_search(description_value: QueryValue) -> list[Q]:
    value_is_digit = description_value.value.isdigit()
    match description_value.operator:
        case ':' if not value_is_digit:
            steps_query = Q(description__icontains=description_value.value)
        case '=' if not value_is_digit:
            steps_query = Q(description__iexact=description_value.value)
        case '<' if value_is_digit:
            steps_query = Q(description_line_count__lt=description_value.value)
        case '<=' if value_is_digit:
            steps_query = Q(description_line_count__lte=description_value.value)
        case '>' if value_is_digit:
            steps_query = Q(description_line_count__gt=description_value.value)
        case '>=' if value_is_digit:
            steps_query = Q(description_line_count__gte=description_value.value)
        case ':' | '=' if value_is_digit:
            steps_query = Q(description_line_count=description_value.value)
        case _:
            raise NotSupportedError(f'Operator {description_value.operator} is not supported for prerequisites search.')
    return [steps_query, Q(status=Variant.Status.OK)]


def results_search(results_value: QueryValue) -> list[Q]:
    value_is_digit = results_value.value.isdigit()
    match results_value.operator:
        case ':' if not value_is_digit:
            results_query = Q(produces__name__icontains=results_value.value)
        case '=' if not value_is_digit:
            results_query = Q(produces__name__iexact=results_value.value)
        case '<' if value_is_digit:
            results_query = Q(results_count__lt=results_value.value)
        case '<=' if value_is_digit:
            results_query = Q(results_count__lte=results_value.value)
        case '>' if value_is_digit:
            results_query = Q(results_count__gt=results_value.value)
        case '>=' if value_is_digit:
            results_query = Q(results_count__gte=results_value.value)
        case ':' | '=' if value_is_digit:
            results_query = Q(results_count=results_value.value)
        case _:
            raise NotSupportedError(f'Operator {results_value.operator} is not supported for results search with {"numbers" if value_is_digit else "strings"}.')
    return [results_query]


def tag_search(tag_value: QueryValue) -> list[Q]:
    if tag_value.operator != ':':
        raise NotSupportedError(f'Operator {tag_value.operator} is not supported for tag search.')
    match tag_value.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            tag_query = Q(spoiler=True)
        case 'commander':
            tag_query = Q(cardinvariant__must_be_commander=True)
        case 'reserved':
            tag_query = Q(uses__reserved=True)
        case 'mandatory':
            tag_query = Q(produces__name='Mandatory Loop')
        case 'lock':
            tag_query = Q(produces__name='Lock')
        case 'infinite':
            tag_query = Q(produces__name='Infinite')
        case 'risky' | 'allin':
            tag_query = Q(produces__name='Risky')
        case 'winning' | 'gamewinning' | 'win':
            tag_query = Q(produces__name__in=[
                'Win the game',
                'Win the game at the beginning of your next upkeep',
                'Each opponent loses the game',
            ])
        case 'featured':
            featured_sets = {s.strip().lower() for s in WebsiteProperty.objects.get(key=FEATURED_SET_CODES).value.split(',')}
            tag_query = Q(uses__latest_printing_set__in=featured_sets, uses__reprinted=False)
        case _:
            raise NotSupportedError(f'Value {tag_value.value} is not supported for tag search.')
    return [tag_query]


def spellbook_id_search(spellbook_id_value: QueryValue) -> list[Q]:
    match spellbook_id_value.operator:
        case ':' | '=':
            spellbook_id_query = Q(id__iexact=spellbook_id_value.value) | Q(aliases__id__iexact=spellbook_id_value.value)
        case _:
            raise NotSupportedError(f'Operator {spellbook_id_value.operator} is not supported for spellbook id search.')
    return [spellbook_id_query]


def commander_name_search(commander_name_value: QueryValue) -> list[Q]:
    match commander_name_value.operator:
        case ':':
            card_query = Q(cardinvariant__card__name__icontains=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented__icontains=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented_simplified__icontains=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented_simplified_with_spaces__icontains=commander_name_value.value)
        case '=':
            card_query = Q(cardinvariant__card__name__iexact=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented__iexact=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented_simplified__iexact=commander_name_value.value) \
                | Q(cardinvariant__card__name_unaccented_simplified_with_spaces__iexact=commander_name_value.value)
        case _:
            raise NotSupportedError(f'Operator {commander_name_value.operator} is not supported for commander name search.')
    return [Q(cardinvariant__must_be_commander=True), card_query]


def legality_search(legality_value: QueryValue) -> list[Q]:
    if legality_value.operator != ':':
        raise NotSupportedError(f'Operator {legality_value.operator} is not supported for legality search.')
    format = legality_value.value.lower()
    supported_formats = {f.removeprefix('legal_') for f in Variant.legalities_fields()}
    if format not in supported_formats:
        raise NotSupportedError(f'Format {format} is not supported for legality search.')
    q = Q(**{f'legal_{format}': True})
    match legality_value.key.lower():
        case 'banned':
            q = ~q
    return [q]


def price_search(price_value: QueryValue) -> list[Q]:
    match price_value.key.lower():
        case 'usd' | 'price':
            store = 'cardkingdom'
        case 'eur':
            store = 'cardmarket'
        case other:
            store = other
    supported_stores = {s.removeprefix('price_') for s in Variant.prices_fields()}
    if store not in supported_stores:
        raise NotSupportedError(f'Store {store} is not supported for price search.')
    if not price_value.value.isdigit():
        raise NotSupportedError(f'Value {price_value.value} is not supported for price search.')
    match price_value.operator:
        case ':' | '=':
            q = Q(**{f'price_{store}': price_value.value})
        case '<':
            q = Q(**{f'price_{store}__lt': price_value.value})
        case '<=':
            q = Q(**{f'price_{store}__lte': price_value.value})
        case '>':
            q = Q(**{f'price_{store}__gt': price_value.value})
        case '>=':
            q = Q(**{f'price_{store}__gte': price_value.value})
        case _:
            raise NotSupportedError(f'Operator {price_value.operator} is not supported for price search.')
    return [q]


def popularity_search(popularity_value: QueryValue) -> list[Q]:
    if not popularity_value.value.isdigit():
        raise NotSupportedError(f'Value {popularity_value.value} is not supported for popularity search.')
    match popularity_value.operator:
        case ':' | '=':
            popularity_query = Q(popularity=popularity_value.value)
        case '<':
            popularity_query = Q(popularity__lt=popularity_value.value)
        case '<=':
            popularity_query = Q(popularity__lte=popularity_value.value)
        case '>':
            popularity_query = Q(popularity__gt=popularity_value.value)
        case '>=':
            popularity_query = Q(popularity__gte=popularity_value.value)
        case _:
            raise NotSupportedError(f'Operator {popularity_value.operator} is not supported for popularity search.')
    return [popularity_query]


keyword_map: dict[str, Callable[[QueryValue], list[Q]]] = {
    'card': card_search,
    'cardtype': card_type_search,
    'cardoracle': card_oracle_search,
    'cardkeywords': card_keyword_search,
    'cardmanavalue': card_mana_value_search,
    'coloridentity': identity_search,
    'prerequisites': prerequisites_search,
    'steps': description_search,
    'results': results_search,
    'spellbookid': spellbook_id_search,
    'is': tag_search,
    'commander': commander_name_search,
    'legal': legality_search,
    'price': price_search,
    'popularity': popularity_search,
}


alias_map: dict[str, str] = {
    'cards': 'card',
    'identity': 'coloridentity',
    'color': 'coloridentity',
    'colors': 'coloridentity',
    'id': 'coloridentity',
    'ids': 'coloridentity',
    'c': 'coloridentity',
    'ci': 'coloridentity',
    'prerequisite': 'prerequisites',
    'prereq': 'prerequisites',
    'pre': 'prerequisites',
    'step': 'steps',
    'description': 'steps',
    'desc': 'steps',
    'result': 'results',
    'sid': 'spellbookid',
    'format': 'legal',
    'banned': 'legal',
    'usd': 'price',
    'eur': 'price',
    **{s.removeprefix('price_'): 'price' for s in Variant.prices_fields()},
    'pop': 'popularity',
    'deck': 'popularity',
    'decks': 'popularity',
    'type': 'cardtype',
    'types': 'cardtype',
    't': 'cardtype',
    'oracle': 'cardoracle',
    'text': 'cardoracle',
    'o': 'cardoracle',
    'cardkeyword': 'cardkeywords',
    'keyword': 'cardkeywords',
    'keywords': 'cardkeywords',
    'kw': 'cardkeywords',
    'manavalue': 'cardmanavalue',
    'mv': 'cardmanavalue',
    'cmc': 'cardmanavalue',
}


SHORT_VALUE_REGEX = r'''(?:[a-zA-Z0-9À-ÿ_\-',+!.])+'''
LONG_VALUE_REGEX = r'(?:[^"\\]|\\")+'
QUERY_REGEX = r'(?:\s|^)(?:(?P<card_short>)|"(?P<card_long>)"|(?P<prefix>-?)(?P<key>[a-zA-Z_]+)(?P<operator>:|=|<|>|<=|>=)(?:(?P<value_short>)|"(?P<value_long>)"))(?=\s|$)' \
    .replace(
        '(?P<card_short>)', f'(?P<card_short>{SHORT_VALUE_REGEX})'
    ).replace(
        '(?P<card_long>)', f'(?P<card_long>{LONG_VALUE_REGEX})'
    ).replace(
        '(?P<value_short>)', f'(?P<value_short>{SHORT_VALUE_REGEX})'
    ).replace(
        '(?P<value_long>)', f'(?P<value_long>{LONG_VALUE_REGEX})'
    )
MAX_QUERY_MATCHES = 30
MAX_QUERY_PARAMETERS = 20


class NotSupportedError(Exception):
    pass


def variants_query_parser_filter(base: QuerySet[Variant], query_string: str) -> QuerySet[Variant]:
    query_string = query_string.strip()
    regex_matches = re.finditer(QUERY_REGEX, query_string)
    parsed_queries = defaultdict[str, list[QueryValue]](list)
    query_match_count = 0
    for regex_match in regex_matches:
        query_match_count += 1
        if query_match_count > MAX_QUERY_MATCHES:
            raise NotSupportedError('Too many search terms.')
        group_dict = regex_match.groupdict()
        if group_dict['card_short'] or group_dict['card_long']:
            card_term = group_dict['card_short'] or group_dict['card_long']
            card_term = card_term.replace('\\', '')
            parsed_queries['card'].append(QueryValue('', '', ':', card_term))
        elif group_dict['key']:
            key = group_dict['key'].lower()
            original_key = key
            if key in alias_map:
                key = alias_map[key]
            if key not in keyword_map:
                raise NotSupportedError(f'Key {key} is not supported for query.')
            value_term = group_dict['value_short'] or group_dict['value_long']
            value_term = value_term.replace('\\', '')
            parsed_queries[key].append(QueryValue(group_dict['prefix'], original_key, group_dict['operator'], value_term))
    if len(parsed_queries) > MAX_QUERY_PARAMETERS:
        raise NotSupportedError('Too many search parameters.')
    filters: list[Filter] = []
    for key, values in parsed_queries.items():
        for value in values:
            qq = keyword_map[key](value)
            if value.prefix == '':
                filters.extend(Filter(q=q, positive=True) for q in qq)
            elif value.prefix == '-':
                filters.extend(Filter(q=q, positive=False) for q in qq)
            elif value.prefix != '':
                raise NotSupportedError(f'Prefix {value.prefix} is not supported for {key} search.')
    return smart_apply_filters(base, filters)


def variants_query_parser(base: QuerySet[Variant], query_string: str) -> QuerySet:
    """
    Parses a query string and filters a queryset of Variants.
    Does not support parentheses.
    Does not support or queries.
    """
    filtered_queryset = variants_query_parser_filter(base, query_string)
    return base.filter(id__in=filtered_queryset.values('id').distinct())
