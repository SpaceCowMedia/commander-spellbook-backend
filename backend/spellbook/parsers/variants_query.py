import re
from django.db.models import Q, QuerySet, Count, Case, When, Value
from django.db.models.functions import Length
from collections import defaultdict
from typing import Callable
from dataclasses import dataclass
from spellbook.models import Variant
from .color_parser import parse_identity


@dataclass
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str


def card_search(card_value: QueryValue) -> Q:
    value_is_digit = card_value.value.isdigit()
    match card_value.operator:
        case ':' if not value_is_digit:
            card_query = Q(uses__name__icontains=card_value.value) | Q(uses__name_unaccented__icontains=card_value.value)
        case '=' if not value_is_digit:
            card_query = Q(uses__name__iexact=card_value.value) | Q(uses__name_unaccented__iexact=card_value.value)
        case '<' if value_is_digit:
            card_query = Q(cards_count__lt=card_value.value)
        case '>' if value_is_digit:
            card_query = Q(cards_count__gt=card_value.value)
        case '<=' if value_is_digit:
            card_query = Q(cards_count__lte=card_value.value)
        case '>=' if value_is_digit:
            card_query = Q(cards_count__gte=card_value.value)
        case '=' if value_is_digit:
            card_query = Q(cards_count=card_value.value)
        case _:
            raise NotSupportedError(f'Operator {card_value.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
    return card_query


def identity_search(identity_value: QueryValue) -> Q:
    value_is_digit = identity_value.value.isdigit()
    identity = ''
    not_in_identity = ''
    if not value_is_digit:
        upper_value = parse_identity(identity_value.value)
        if upper_value is None:
            raise NotSupportedError(f'Invalid color identity: {identity_value.value}')
        for color in 'WURBG':
            if color in upper_value:
                identity += color
            else:
                not_in_identity += color
    match identity_value.operator:
        case ':' if not value_is_digit:
            identity_query = Q(identity=identity or 'C')
        case '=' if not value_is_digit:
            identity_query = Q(identity=identity or 'C')
        case '<' if not value_is_digit:
            identity_query = Q(identity_count__lt=len(identity))
            for color in not_in_identity:
                identity_query = ~Q(identity__contains=color)
        case '<=' if not value_is_digit:
            identity_query = Q(identity_count__lte=len(identity))
            for color in not_in_identity:
                identity_query = ~Q(identity__contains=color)
        case '>' if not value_is_digit:
            identity_query = Q(identity_count__gt=len(identity))
            for color in identity:
                identity_query = Q(identity__contains=color)
        case '>=' if not value_is_digit:
            identity_query = Q(identity_count__gte=len(identity))
            for color in identity:
                identity_query = Q(identity__contains=color)
        case '=' if value_is_digit:
            identity_query = Q(identity_count=identity_value.value)
        case '<' if value_is_digit:
            identity_query = Q(identity_count__lt=identity_value.value)
        case '<=' if value_is_digit:
            identity_query = Q(identity_count__lte=identity_value.value)
        case '>' if value_is_digit:
            identity_query = Q(identity_count__gt=identity_value.value)
        case '>=' if value_is_digit:
            identity_query = Q(identity_count__gte=identity_value.value)
        case _:
            raise NotSupportedError(f'Operator {identity_value.operator} is not supported for identity search with {"numbers" if value_is_digit else "strings"}.')
    return identity_query


def prerequisites_search(prerequisites_value: QueryValue) -> Q:
    match prerequisites_value.operator:
        case ':':
            prerequisites_query = Q(other_prerequisites__icontains=prerequisites_value.value)
        case _:
            raise NotSupportedError(f'Operator {prerequisites_value.operator} is not supported for prerequisites search.')
    return prerequisites_query


def steps_search(steps_value: QueryValue) -> Q:
    match steps_value.operator:
        case ':':
            steps_query = Q(description__icontains=steps_value.value)
        case _:
            raise NotSupportedError(f'Operator {steps_value.operator} is not supported for prerequisites search.')
    return steps_query


def results_search(results_value: QueryValue) -> Q:
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
        case '=' if value_is_digit:
            results_query = Q(results_count=results_value.value)
        case _:
            raise NotSupportedError(f'Operator {results_value.operator} is not supported for results search with {"numbers" if value_is_digit else "strings"}.')
    return results_query


def tag_search(tag_value: QueryValue) -> Q:
    if tag_value.operator != ':':
        raise NotSupportedError(f'Operator {tag_value.operator} is not supported for tag search.')
    match tag_value.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            tag_query = Q(spoiler=True)
        case 'commander':
            tag_query = Q(cardinvariant__must_be_commander=True)
        case 'mandatory':
            tag_query = Q(produces__name='Mandatory Loop')
        case 'lock':
            tag_query = Q(produces__name='Lock')
        case 'infinite':
            tag_query = Q(produces__name='Infinite')
        case 'risky' | 'allin':
            tag_query = Q(produces__name='Risky')
        case 'winning' | 'gamewinning':
            tag_query = Q(produces__name__in=['Win the game', 'Win the game at the beginning of your next upkeep'])
        case _:
            raise NotSupportedError(f'Value {tag_value.value} is not supported for tag search.')
    return tag_query


def spellbook_id_search(spellbook_id_value: QueryValue) -> Q:
    match spellbook_id_value.operator:
        case ':' | '=':
            spellbook_id_query = Q(id__istartswith=spellbook_id_value.value)
        case _:
            raise NotSupportedError(f'Operator {spellbook_id_value.operator} is not supported for spellbook id search.')
    return spellbook_id_query


def commander_name_search(commander_name_value: QueryValue) -> Q:
    match commander_name_value.operator:
        case ':':
            commander_name_query = Q(cardinvariant__must_be_commander=True, cardinvariant__card__name__icontains=commander_name_value.value)
        case '=':
            commander_name_query = Q(cardinvariant__must_be_commander=True, cardinvariant__card__name__iexact=commander_name_value.value)
        case _:
            raise NotSupportedError(f'Operator {commander_name_value.operator} is not supported for commander name search.')
    return commander_name_query


def legality_search(legality_value: QueryValue) -> Q:
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
    return q


def price_search(price_value: QueryValue) -> Q:
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
    return q


keyword_map: dict[str, Callable[[QueryValue], Q]] = {
    'card': card_search,
    'coloridentity': identity_search,
    'prerequisites': prerequisites_search,
    'steps': steps_search,
    'results': results_search,
    'spellbookid': spellbook_id_search,
    'is': tag_search,
    'commander': commander_name_search,
    'legal': legality_search,
    'price': price_search,
}


alias_map: dict[str, str] = {
    'cards': 'card',
    'color_identity': 'coloridentity',
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
}


QUERY_REGEX = r'(?:\s|^)(?:(?P<card_short>[a-zA-ZÀ-ÿ]+)|"(?P<card_long>[^"]+)"|(?P<prefix>-?)(?P<key>[a-zA-Z]+)(?P<operator>:|=|<|>|<=|>=)(?:(?P<value_short>[a-zA-Z0-9À-ÿ]+)|"(?P<value_long>[^"]+)"))(?=\s|$)'


class NotSupportedError(Exception):
    pass


def variants_query_parser(base: QuerySet, query_string: str) -> QuerySet:
    """
    Parse a query string into a Django Q object.
    """
    query_string = query_string.strip()
    regex_matches = re.finditer(QUERY_REGEX, query_string)
    parsed_queries = defaultdict[str, list[QueryValue]](list)
    queryset = base \
        .alias(cards_count=Count('uses', distinct=True)) \
        .alias(identity_count=Case(When(identity='C', then=Value(0)), default=Length('identity'))) \
        .alias(results_count=Count('produces', distinct=True))
    for regex_match in regex_matches:
        group_dict = regex_match.groupdict()
        if group_dict['card_short'] or group_dict['card_long']:
            card_term = group_dict['card_short'] or group_dict['card_long']
            parsed_queries['card'].append(QueryValue('', '', ':', card_term))
        elif group_dict['key']:
            key = group_dict['key']
            original_key = key
            if key in alias_map:
                key = alias_map[key]
            if key not in keyword_map:
                raise NotSupportedError(f'Key {key} is not supported for query.')
            parsed_queries[key].append(QueryValue(group_dict['prefix'], original_key, group_dict['operator'], group_dict['value_short'] or group_dict['value_long']))
    if len(parsed_queries) > 20:
        raise NotSupportedError('Too many search terms.')
    for key, values in parsed_queries.items():
        for value in values:
            q = keyword_map[key](value)
            if value.prefix == '-':
                q = ~q
            elif value.prefix != '':
                raise NotSupportedError(f'Prefix {value.prefix} is not supported for {key} search.')
            queryset = queryset.filter(q)
    return queryset
