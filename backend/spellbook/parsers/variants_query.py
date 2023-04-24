import re
from django.db.models import Q, QuerySet, Count
from collections import namedtuple, defaultdict
from typing import Callable


QueryValue = namedtuple('QueryValue', ['prefix', 'operator', 'value'])


def card_search(q: QuerySet, cards: list[QueryValue]) -> QuerySet:
    q = q.annotate(uses_count=Count('uses', distinct=True))
    for card in cards:
        card_query = Q()
        value_is_digit = card.value.isdigit()
        match card.operator:
            case ':' if not value_is_digit:
                card_query &= Q(uses__name__icontains=card.value)
            case '=' if not value_is_digit:
                card_query &= Q(uses__name__iexact=card.value)
            case '<' if value_is_digit:
                card_query &= Q(uses_count__lt=card.value)
            case '>' if value_is_digit:
                card_query &= Q(uses_count__gt=card.value)
            case '<=' if value_is_digit:
                card_query &= Q(uses_count__lte=card.value)
            case '>=' if value_is_digit:
                card_query &= Q(uses_count__gte=card.value)
            case '=' if value_is_digit:
                card_query &= Q(uses_count=card.value)
            case _:
                raise NotSupportedError(f'Operator {card.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
        if card.prefix == '-':
            card_query = ~card_query
        elif card.prefix != '':
            raise NotSupportedError(f'Prefix {card.prefix} is not supported for card search.')
        q = q.filter(card_query)
    return q


keyword_map: dict[str, Callable[[QuerySet, list[QueryValue]], QuerySet]] = {
    'card': card_search,
}


alias_map: dict[str, str] = {
    'cards': 'card',
}


QUERY_REGEX = r'(?:\s|^)(?:(?P<card_short>[a-zA-Z]+)|"(?P<card_long>[^"]+)"|(?P<prefix>-?)(?P<key>[a-zA-Z]+)(?P<operator>:|=|<|>|<=|>=)(?:(?P<value_short>[a-zA-Z0-9]+)|"(?P<value_long>[^"]+)"))(?=\s|$)'


class NotSupportedError(Exception):
    pass


def variants_query_parser(base: QuerySet, query_string: str) -> QuerySet:
    """
    Parse a query string into a Django Q object.
    """
    query_string = query_string.strip()
    regex_matches = re.finditer(QUERY_REGEX, query_string)
    parsed_queries = defaultdict[str, list[QueryValue]](list)
    queryset = base
    for regex_match in regex_matches:
        group_dict = regex_match.groupdict()
        if group_dict['card_short'] or group_dict['card_long']:
            card_term = group_dict['card_short'] or group_dict['card_long']
            parsed_queries['card'].append(QueryValue('', ':', card_term))
        elif group_dict['key']:
            key = group_dict['key']
            if key in alias_map:
                key = alias_map[key]
            if key not in keyword_map:
                raise NotSupportedError(f'Key {key} is not supported for query.')
            parsed_queries[key].append(QueryValue(group_dict['prefix'], group_dict['operator'], group_dict['value_short'] or group_dict['value_long']))
    for key, values in parsed_queries.items():
        queryset = keyword_map[key](queryset, values)
    return queryset
