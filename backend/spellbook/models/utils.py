import re
import unicodedata
from typing import Callable, Generator, Iterable
from collections import defaultdict
from ..regexs import MANA_SYMBOL, ORACLE_SYMBOL, ORACLE_SYMBOL_EXTENDED
from ..parsers.scryfall_query_grammar import COMPARISON_OPERATORS, MANA_COMPARABLE_VARIABLES
from django.utils.text import normalize_newlines
from django.db import connection
from django.db.models import Expression, F, Value, TextChoices, OrderBy
from django.db.models.functions import Replace, Trim
from constants import SORTED_COLORS, COLORS


MANA_SEARCH_REGEX = r'\{(' + MANA_SYMBOL + r')\}'
SANITIZATION_REPLACEMENTS = {
    'ʹʻʼʾˈ՚′＇ꞌ': '\'',  # apostrophes
    'ʻʼ‘’❛❜': '\'',  # quotes
    '“”″❞〝〞ˮ': '"',  # double quotes
}

MANA_COST_PATTERN = re.compile(r'^(?:\s*' + MANA_SEARCH_REGEX + r')*\s*$', re.IGNORECASE)
MANA_SEARCH_PATTERN = re.compile(MANA_SEARCH_REGEX, re.IGNORECASE)
MANA_PREFIX_PATTERN = re.compile(r'(^(?:\s*' + MANA_SEARCH_REGEX + r')*)', re.IGNORECASE)
ORACLE_SYMBOL_PATTERN = re.compile(r'\{' + ORACLE_SYMBOL + r'\}', re.IGNORECASE)
ORACLE_SYMBOL_EXTENDED_FULL_PATTERN = re.compile(r'^' + ORACLE_SYMBOL_EXTENDED + r'+$', re.IGNORECASE)
ORACLE_SYMBOL_EXTENDED_BRACES_PATTERN = re.compile(r'\{?(' + ORACLE_SYMBOL_EXTENDED + r')\}?', re.IGNORECASE)
HYBRID_MANA_TWO_SYMBOL_PATTERN = re.compile(r'\{([WUBRGCP2])([WUBRGCP2])\}', re.IGNORECASE)
HYBRID_MANA_THREE_SYMBOL_PATTERN = re.compile(r'\{([WUBRGCP2])([WUBRGCP2])([WUBRGCP2])\}', re.IGNORECASE)
SCRYFALL_FORMAT_FILTER_PATTERN = re.compile(r'(?:^|\s+)-?(?:f|format|legal):[^\s]+(?=\s|$)', re.IGNORECASE)
MANA_COMPARABLE_FILTER_PATTERN = re.compile(rf'(^|\s+)(-?(?:{'|'.join(MANA_COMPARABLE_VARIABLES)}))((?:{'|'.join(COMPARISON_OPERATORS)}))([^\s]+)(?=\s|$)', re.IGNORECASE)


class CardType(TextChoices):
    CREATURE = 'Creature', 'Creature'
    ARTIFACT = 'Artifact', 'Artifact'
    ENCHANTMENT = 'Enchantment', 'Enchantment'
    PLANESWALKER = 'Planeswalker', 'Planeswalker'
    INSTANT = 'Instant', 'Instant'
    SORCERY = 'Sorcery', 'Sorcery'
    LAND = 'Land', 'Land'
    BATTLE = 'Battle', 'Battle'
    LEGENDARY = 'Legendary', 'Legendary'


def recipe(ingredients: list[str], results: list[str], negative_results: list[str] = []):
    return ' + '.join(ingredients) \
        + ' ➜ ' + ' + '.join(results[:3]) \
        + ('...' if len(results) > 3 else '') \
        + (' - ' + ' - '.join(negative_results[:3 - len(results)]) if negative_results and len(results) < 3 else '') \
        + ('...' if len(negative_results) > 3 and len(results) < 3 else '')


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def id_from_cards_and_templates_ids(cards: Iterable[int], templates: Iterable[int]) -> str:
    sorted_templates = sorted(templates)
    return '-'.join(str(c) for c in sorted(cards)) + ('--' + '--'.join(str(t) for t in sorted_templates) if len(sorted_templates) > 0 else '')


def sort_color_identity_set(identity_set: frozenset[str]) -> str:
    return SORTED_COLORS[identity_set or frozenset('C')]


def sort_color_identity(identity: str) -> str:
    identity_set = frozenset(identity.upper()).intersection(COLORS)
    return sort_color_identity_set(identity_set)


def merge_color_identities(identities: Iterable[str]) -> str:
    return sort_color_identity(''.join(identities))


def get_color_or_empty(x: str) -> str:
    s = x.upper()
    return s if s in COLORS else ''


def sort_by_identity(sequence: Iterable[str], color: Callable[[str], str]) -> list[str]:
    tuples = [(x, get_color_or_empty(color(x))) for x in sequence]
    identity = sort_color_identity_set(frozenset(c for _, c in tuples if c))
    return [s for s, _ in sorted(tuples, key=lambda t: -1 if t[1] == '' else identity.index(t[1]))]


def join_with_conjunction(strings: Iterable[str], conjunction: str = 'and') -> str:
    '''Joins non-empty strings into a sentence like "a, b and c", with the given conjunction before the last item.'''
    strings = [s for s in strings if s]
    match len(strings):
        case 0:
            return ''
        case 1:
            return strings[0]
        case _:
            return f'{', '.join(strings[:-1])} {conjunction} {strings[-1]}'


def merge_mana_costs(mana_costs: Iterable[str]) -> str:
    costs = defaultdict[str, int](int)
    strings: list[str] = []
    for mana_cost in mana_costs:
        mana_cost = sanitize_mana(mana_cost.strip().removesuffix('.').strip())
        if MANA_COST_PATTERN.fullmatch(mana_cost):
            for matching_symbol in MANA_SEARCH_PATTERN.findall(mana_cost):
                match matching_symbol:
                    case n if matching_symbol.isdigit():
                        costs['1'] += int(n)
                    case _:
                        costs[matching_symbol] += 1
        else:
            strings.append(mana_cost)
    if costs:
        cost_string = ''

        def process_symbol(symbol: str):
            nonlocal cost_string
            if symbol in costs:
                cost_string += f'{{{symbol}}}' * costs[symbol]
                del costs[symbol]

        # Specification: https://www.reddit.com/r/custommagic/comments/1nhtr3w/guide_for_formatting_mana_costs/
        # Variable generic mana symbols
        for symbol in 'XYZ':
            process_symbol(symbol)
        # Numbered generic mana symbols, merged into a single symbol; {0} contributes nothing
        if '1' in costs:
            count = costs['1']
            del costs['1']
            if count > 0:
                cost_string += f'{{{count}}}'
        # Group symbols by their leftmost half
        grouped_symbols = defaultdict[str, list[str]](list)
        for symbol in costs.keys():
            key = symbol.split('/')[0]
            grouped_symbols[key].append(symbol)
        # Numbered colorless hybrid mana symbols
        symbols = grouped_symbols.pop('2', [])
        for symbol in sort_by_identity(symbols, lambda s: s[-1]):
            process_symbol(symbol)
        # Colorless mana symbols
        symbols = grouped_symbols.pop('C', [])
        for symbol in sort_by_identity(symbols, lambda s: s[-1]):
            process_symbol(symbol)
        # Colored mana symbols sorted
        identity = sort_color_identity_set(COLORS.intersection(grouped_symbols))
        for color in identity:
            # Group by color
            symbols = grouped_symbols.pop(color, [])
            hybrid = list[str]()
            non_hybrid = list[str]()
            # Separate hybrid and non-hybrid symbols
            for symbol in symbols:
                identity = COLORS.intersection(symbol)
                match len(identity):
                    case 1:
                        non_hybrid.append(symbol)
                    case _:
                        hybrid.append(symbol)
            # Re-arrange such that normal mana precedes phyrexian mana
            non_hybrid.sort(key=lambda s: (len(s), s))
            # Colored mana precedes hybrid mana
            for symbol in non_hybrid:
                process_symbol(symbol)
            # Re-arrange such that normal mana precedes phyrexian mana
            hybrid.sort(key=lambda s: (len(s), s))
            # Re-arrange such that the leftmost halves are sorted
            hybrid = sort_by_identity(hybrid, lambda s: s.split('/')[1])
            for symbol in hybrid:
                process_symbol(symbol)
        # Snow mana symbols and eventual weird symbols at the end
        for symbol in sorted(costs.keys(), key=lambda s: (len(s), s)):
            cost_string += f'{{{symbol}}}' * costs[symbol]
        strings.insert(0, cost_string)
    strings = [s for s in strings if s]
    match len(strings):
        case 2 if not any(' plus ' in s for s in strings):
            return join_with_conjunction(strings, conjunction='plus')
        case 2 if not any(' and ' in s for s in strings):
            return join_with_conjunction(strings)
        case _:
            return ', '.join(strings)


def mana_value(mana: str) -> int:
    value = 0
    mana_cut_match = MANA_PREFIX_PATTERN.search(mana)
    if mana_cut_match:
        mana_cut = mana_cut_match.group(0)
        for mana in MANA_SEARCH_PATTERN.findall(mana_cut):
            match mana:
                case n if mana.isdigit():
                    value += int(n)
                case 'X' | 'Y' | 'Z':
                    pass
                case '∞':
                    value += 1_000_000
                case _:
                    value += 1
    return value


def upper_oracle_symbols(text: str):
    return ORACLE_SYMBOL_PATTERN.sub(lambda m: m.group(0).upper(), text)


def auto_fix_reverse_hybrid_mana(text: str):
    def replace_reversed(text: str, color_combo: str):
        return re.sub(r'\{' + '/'.join(reversed(color_combo)) + r'\}', r'{' + '/'.join(color_combo) + r'}', text, flags=re.IGNORECASE)
    for color_combo in SORTED_COLORS.values():
        match len(color_combo):
            case 1:
                text = replace_reversed(text, f'2{color_combo}')
                text = replace_reversed(text, f'{color_combo}P')
                text = replace_reversed(text, f'C{color_combo}')
            case 2:
                text = replace_reversed(text, color_combo)
    return text


def auto_fix_missing_braces_to_oracle_symbols(text: str):
    if ORACLE_SYMBOL_EXTENDED_FULL_PATTERN.match(text):
        return ORACLE_SYMBOL_EXTENDED_BRACES_PATTERN.sub(r'{\1}', text)
    return text


def auto_fix_missing_slashes_in_hybrid_mana(text: str):
    text = HYBRID_MANA_TWO_SYMBOL_PATTERN.sub(r'{\1/\2}', text)
    text = HYBRID_MANA_THREE_SYMBOL_PATTERN.sub(r'{\1/\2/\3}', text)
    return text


def sanitize_mana(mana: str) -> str:
    mana = auto_fix_missing_braces_to_oracle_symbols(mana)
    mana = auto_fix_missing_slashes_in_hybrid_mana(mana)
    mana = auto_fix_reverse_hybrid_mana(mana)
    mana = upper_oracle_symbols(mana)
    return mana


def sanitize_scryfall_query(text: str):
    text = SCRYFALL_FORMAT_FILTER_PATTERN.sub('', text)
    text = text.strip()
    text = MANA_COMPARABLE_FILTER_PATTERN.sub(lambda m: f'{m[1]}{m[2]}{m[3]}{sanitize_mana(m[4])}', text)
    text = text.strip()
    return text


def sanitize_newlines_apostrophes_and_quotes(s: str) -> str:
    s = normalize_newlines(s)
    for chars, replacement in SANITIZATION_REPLACEMENTS.items():
        for c in chars:
            s = s.replace(c, replacement)
    return s


def simplify_card_name_on_database(field: str) -> Expression:
    return Trim(
        Replace(
            Replace(
                F(field),
                Value('-'),
                Value('')
            ),
            Value('_____'),
            Value('')
        )
    )


def simplify_card_name_with_spaces_on_database(field: str) -> Expression:
    return Trim(
        Replace(
            Replace(
                F(field),
                Value('-'),
                Value(' ')
            ),
            Value('_____'),
            Value('_')
        )
    )


def remove_duplicates_in_order_by(order_by: Iterable[str | F | OrderBy]) -> Generator[F | OrderBy, None, None]:
    seen = set()
    for o in order_by:
        if isinstance(o, str):
            name = o.removeprefix('-')
            o = F(name)
        elif isinstance(o, F):
            name = o.name.removeprefix('-')
        elif isinstance(o, OrderBy) and isinstance(o.expression, F):
            name = o.expression.name.removeprefix('-')
        else:
            raise ValueError(f'Unknown order by type: {o}')
        if name not in seen:
            seen.add(name)
            yield o


def remove_random_from_order_by(order_by: Iterable[str | F | OrderBy]) -> Generator[F | OrderBy, None, None]:
    for o in order_by:
        if isinstance(o, str):
            if o == '?':
                continue
            o = F(o)
        elif isinstance(o, F):
            if o.name == '?':
                continue
        elif isinstance(o, OrderBy) and isinstance(o.expression, F):
            if o.expression.name == '?':
                continue
        else:
            raise ValueError(f'Unknown order by type: {o}')
        yield o


def __default_batch_size() -> int:
    '''Returns an appropriate batch size for the current database connection.'''
    otherwise = 100
    match connection.vendor:
        case 'sqlite':
            return 200
        case 'postgresql':
            return 275
        case _:
            return otherwise


DEFAULT_BATCH_SIZE = __default_batch_size()
