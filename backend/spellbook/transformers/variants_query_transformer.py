import re
from typing import Callable
from collections import defaultdict
from dataclasses import dataclass
from django.db.models import Q, QuerySet
from spellbook.models import Variant, FeatureProducedByVariant, CardInVariant
from website.models import WebsiteProperty, FEATURED_SET_CODES
from ..parsers.color_parser import parse_identity
from ..parsers.variants_query_grammar import VARIANTS_QUERY_GRAMMAR
from lark import Lark, Transformer


class VariantsQueryTransformer(Transformer):
    def card_search_shortcut(self, values):
        return None

    def card_search(self, values):
        return None

    def card_type_search(self, values):
        return None

    def card_oracle_search(self, values):
        return None

    def card_keyword_search(self, values):
        return None

    def card_mana_value_search(self, values):
        return None

    def identity_search(self, values):
        return None

    def prerequisites_search(self, values):
        return None

    def steps_search(self, values):
        return None

    def results_search(self, values):
        return None

    def spellbook_id_search(self, values):
        return None

    def tag_search(self, values):
        return None

    def commander_search(self, values):
        return None

    def legality_search(self, values):
        return None

    def price_search(self, values):
        return None

    def popularity_search(self, values):
        return None

    # composition
    def factor(self, values):
        return None

    def term(self, values):
        return None

    def query(self, values):
        return None

    def start(self, values):
        return None


PARSER = Lark(VARIANTS_QUERY_GRAMMAR, parser='lalr', transformer=VariantsQueryTransformer())


@dataclass(frozen=True)
class QueryValue:
    prefix: str
    key: str
    operator: str
    value: str

    def is_negated(self) -> bool:
        match self.prefix:
            case '':
                return False
            case '-':
                return True
            case _:
                raise NotSupportedError(f'Prefix {self.prefix} is not supported for {self.key} search.')


@dataclass
class VariantFilter:
    q: Q
    on_features_produced: bool = False
    on_cards: bool = False
    negative: bool = False


def card_search(card_value: QueryValue) -> list[VariantFilter]:
    value_is_digit = card_value.value.isdigit()
    match card_value.operator:
        case ':' if not value_is_digit:
            filters = [VariantFilter(
                q=Q(card__name__icontains=card_value.value) | Q(card__name_unaccented__icontains=card_value.value) | Q(card__name_unaccented_simplified__icontains=card_value.value) | Q(card__name_unaccented_simplified_with_spaces__icontains=card_value.value),
                on_cards=True,
                negative=card_value.is_negated(),
            )]
        case '=' if not value_is_digit:
            filters = [VariantFilter(
                q=Q(card__name__iexact=card_value.value) | Q(card__name_unaccented__iexact=card_value.value) | Q(card__name_unaccented_simplified__iexact=card_value.value) | Q(card__name_unaccented_simplified_with_spaces__iexact=card_value.value),
                on_cards=True,
                negative=card_value.is_negated(),
            )]
        case '<' if value_is_digit:
            filters = [VariantFilter(
                q=Q(cards_count__lt=card_value.value),
                negative=card_value.is_negated(),
            )]
        case '>' if value_is_digit:
            filters = [VariantFilter(
                q=Q(cards_count__gt=card_value.value),
                negative=card_value.is_negated(),
            )]
        case '<=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(cards_count__lte=card_value.value),
                negative=card_value.is_negated(),
            )]
        case '>=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(cards_count__gte=card_value.value),
                negative=card_value.is_negated(),
            )]
        case ':' | '=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(cards_count=card_value.value),
                negative=card_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {card_value.operator} is not supported for card search with {"numbers" if value_is_digit else "strings"}.')
    return filters


def card_type_search(card_type_value: QueryValue) -> list[VariantFilter]:
    match card_type_value.operator:
        case ':':
            filters = [VariantFilter(
                q=Q(card__type_line__icontains=card_type_value.value),
                on_cards=True,
                negative=card_type_value.is_negated(),
            )]
        case '=':
            filters = [VariantFilter(
                q=Q(card__type_line__iexact=card_type_value.value),
                on_cards=True,
                negative=card_type_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {card_type_value.operator} is not supported for card type search.')
    return filters


def card_oracle_search(card_oracle_value: QueryValue) -> list[VariantFilter]:
    match card_oracle_value.operator:
        case ':':
            filters = [VariantFilter(
                q=Q(card__oracle_text__icontains=card_oracle_value.value),
                on_cards=True,
                negative=card_oracle_value.is_negated(),
            )]
        case '=':
            filters = [VariantFilter(
                q=Q(card__oracle_text__iexact=card_oracle_value.value),
                on_cards=True,
                negative=card_oracle_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {card_oracle_value.operator} is not supported for card oracle search.')
    return filters


def card_keyword_search(card_keyword_value: QueryValue) -> list[VariantFilter]:
    match card_keyword_value.operator:
        case ':':
            filters = [VariantFilter(
                q=Q(card__keywords__icontains=card_keyword_value.value),
                on_cards=True,
                negative=card_keyword_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {card_keyword_value.operator} is not supported for card keyword search.')
    return filters


def card_mana_value_search(card_mana_value_value: QueryValue) -> list[VariantFilter]:
    value_is_digit = card_mana_value_value.value.isdigit()
    match card_mana_value_value.operator:
        case ':' | '=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(card__mana_value=card_mana_value_value.value),
                on_cards=True,
                negative=card_mana_value_value.is_negated(),
            )]
        case '<' if value_is_digit:
            filters = [VariantFilter(
                q=Q(card__mana_value__lt=card_mana_value_value.value),
                on_cards=True,
                negative=card_mana_value_value.is_negated(),
            )]
        case '<=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(card__mana_value__lte=card_mana_value_value.value),
                on_cards=True,
                negative=card_mana_value_value.is_negated(),
            )]
        case '>' if value_is_digit:
            filters = [VariantFilter(
                q=Q(card__mana_value__gt=card_mana_value_value.value),
                on_cards=True,
                negative=card_mana_value_value.is_negated(),
            )]
        case '>=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(card__mana_value__gte=card_mana_value_value.value),
                on_cards=True,
                negative=card_mana_value_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {card_mana_value_value.operator} is not supported for card mana value search with {"numbers" if value_is_digit else "strings"}.')
    return filters


def identity_search(identity_value: QueryValue) -> list[VariantFilter]:
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
    return [VariantFilter(q=q, negative=identity_value.is_negated()) for q in identity_queries]


def prerequisites_search(prerequisites_value: QueryValue) -> list[VariantFilter]:
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
    return [VariantFilter(q=prerequisites_query, negative=prerequisites_value.is_negated()), VariantFilter(q=~Q(status=Variant.Status.EXAMPLE))]


def description_search(description_value: QueryValue) -> list[VariantFilter]:
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
    return [VariantFilter(q=steps_query, negative=description_value.is_negated()), VariantFilter(q=~Q(status=Variant.Status.EXAMPLE))]


def results_search(results_value: QueryValue) -> list[VariantFilter]:
    value_is_digit = results_value.value.isdigit()
    match results_value.operator:
        case ':' if not value_is_digit:
            filters = [VariantFilter(
                q=Q(feature__name__icontains=results_value.value),
                on_features_produced=True,
                negative=results_value.is_negated(),
            )]
        case '=' if not value_is_digit:
            filters = [VariantFilter(
                q=Q(feature__name__iexact=results_value.value),
                on_features_produced=True,
                negative=results_value.is_negated(),
            )]
        case '<' if value_is_digit:
            filters = [VariantFilter(
                q=Q(results_count__lt=results_value.value),
                negative=results_value.is_negated(),
            )]
        case '<=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(results_count__lte=results_value.value),
                negative=results_value.is_negated(),
            )]
        case '>' if value_is_digit:
            filters = [VariantFilter(
                q=Q(results_count__gt=results_value.value),
                negative=results_value.is_negated(),
            )]
        case '>=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(results_count__gte=results_value.value),
                negative=results_value.is_negated(),
            )]
        case ':' | '=' if value_is_digit:
            filters = [VariantFilter(
                q=Q(results_count=results_value.value),
                negative=results_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {results_value.operator} is not supported for results search with {"numbers" if value_is_digit else "strings"}.')
    return filters


def tag_search(tag_value: QueryValue) -> list[VariantFilter]:
    if tag_value.operator != ':':
        raise NotSupportedError(f'Operator {tag_value.operator} is not supported for tag search.')
    match tag_value.value.lower():
        case 'preview' | 'previewed' | 'spoiler' | 'spoiled':
            filters = [VariantFilter(
                q=Q(spoiler=True),
                negative=tag_value.is_negated(),
            )]
        case 'commander':
            filters = [VariantFilter(
                q=Q(must_be_commander=True),
                on_cards=True,
                negative=tag_value.is_negated(),
            )]
        case 'reserved':
            filters = [VariantFilter(
                q=Q(card__reserved=True),
                on_cards=True,
                negative=tag_value.is_negated(),
            )]
        case 'mandatory':
            filters = [VariantFilter(
                q=Q(feature__name='Mandatory Loop'),
                on_features_produced=True,
                negative=tag_value.is_negated(),
            )]
        case 'lock':
            filters = [VariantFilter(
                q=Q(feature__name='Lock'),
                on_features_produced=True,
                negative=tag_value.is_negated(),
            )]
        case 'infinite':
            filters = [VariantFilter(
                q=Q(feature__name='Infinite'),
                on_features_produced=True,
                negative=tag_value.is_negated(),
            )]
        case 'risky' | 'allin':
            filters = [VariantFilter(
                q=Q(feature__name='Risky'),
                on_features_produced=True,
                negative=tag_value.is_negated(),
            )]
        case 'winning' | 'gamewinning' | 'win':
            filters = [VariantFilter(
                q=Q(feature__name__in=[
                    'Win the game',
                    'Win the game at the beginning of your next upkeep',
                    'Each opponent loses the game',
                ]),
                on_features_produced=True,
                negative=tag_value.is_negated(),
            )]
        case 'featured':
            featured_sets = {s.strip().lower() for s in WebsiteProperty.objects.get(key=FEATURED_SET_CODES).value.split(',')}
            filters = [VariantFilter(
                q=Q(card__latest_printing_set__in=featured_sets, card__reprinted=False),
                on_cards=True,
                negative=tag_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Value {tag_value.value} is not supported for tag search.')
    return filters


def spellbook_id_search(spellbook_id_value: QueryValue) -> list[VariantFilter]:
    match spellbook_id_value.operator:
        case ':' | '=':
            filters = [VariantFilter(
                q=Q(id__iexact=spellbook_id_value.value) | Q(aliases__id__iexact=spellbook_id_value.value),
                negative=spellbook_id_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {spellbook_id_value.operator} is not supported for spellbook id search.')
    return filters


def commander_name_search(commander_name_value: QueryValue) -> list[VariantFilter]:
    match commander_name_value.operator:
        case ':':
            card_query = Q(card__name__icontains=commander_name_value.value) \
                | Q(card__name_unaccented__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__icontains=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__icontains=commander_name_value.value)
            filters = [VariantFilter(
                q=card_query & Q(must_be_commander=True),
                on_cards=True,
                negative=commander_name_value.is_negated(),
            )]
        case '=':
            card_query = Q(card__name__iexact=commander_name_value.value) \
                | Q(card__name_unaccented__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified__iexact=commander_name_value.value) \
                | Q(card__name_unaccented_simplified_with_spaces__iexact=commander_name_value.value)
            filters = [VariantFilter(
                q=card_query & Q(must_be_commander=True),
                on_cards=True,
                negative=commander_name_value.is_negated(),
            )]
        case _:
            raise NotSupportedError(f'Operator {commander_name_value.operator} is not supported for commander name search.')
    return filters


def legality_search(legality_value: QueryValue) -> list[VariantFilter]:
    if legality_value.operator != ':':
        raise NotSupportedError(f'Operator {legality_value.operator} is not supported for legality search.')
    format = legality_value.value.lower()
    supported_formats = {f.removeprefix('legal_') for f in Variant.legalities_fields()}
    if format not in supported_formats:
        raise NotSupportedError(f'Format {format} is not supported for legality search.')
    legal = True
    match legality_value.key.lower():
        case 'banned':
            legal = False
    q = Q(**{f'legal_{format}': legal})
    return [VariantFilter(q=q, negative=legality_value.is_negated())]


def price_search(price_value: QueryValue) -> list[VariantFilter]:
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
    return [VariantFilter(q=q, negative=price_value.is_negated())]


def popularity_search(popularity_value: QueryValue) -> list[VariantFilter]:
    if not popularity_value.value.isdigit():
        raise NotSupportedError(f'Value {popularity_value.value} is not supported for popularity search.')
    match popularity_value.operator:
        case ':' | '=':
            q = Q(popularity=popularity_value.value)
        case '<':
            q = Q(popularity__lt=popularity_value.value)
        case '<=':
            q = Q(popularity__lte=popularity_value.value)
        case '>':
            q = Q(popularity__gt=popularity_value.value)
        case '>=':
            q = Q(popularity__gte=popularity_value.value)
        case _:
            raise NotSupportedError(f'Operator {popularity_value.operator} is not supported for popularity search.')
    return [VariantFilter(q=q, negative=popularity_value.is_negated())]


keyword_map: dict[str, Callable[[QueryValue], list[VariantFilter]]] = {
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


def variants_query_parser(base: QuerySet[Variant], query_string: str) -> QuerySet:
    query_string = query_string.strip()
    _ = PARSER.parse(query_string)
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
    filtered_variants = base
    for key, values in parsed_queries.items():
        for value in values:
            filters = keyword_map[key](value)
            for filter in filters:
                if filter.on_features_produced:
                    filtered_produces = FeatureProducedByVariant.objects.filter(filter.q)
                    q = Q(pk__in=filtered_produces.values('variant').distinct())
                elif filter.on_cards:
                    filtered_cards = CardInVariant.objects.filter(filter.q)
                    q = Q(pk__in=filtered_cards.values('variant').distinct())
                else:
                    q = filter.q
                filtered_variants = filtered_variants.exclude(q) if filter.negative else filtered_variants.filter(q)
    return filtered_variants
