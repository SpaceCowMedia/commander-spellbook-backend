import re
import unicodedata
from typing import Iterable, Callable
from .validators import MANA_SYMBOL


MANA_SEARCH_REGEX = r'\{(' + MANA_SYMBOL + r')\}'
MANA_PREFIX_REGEX = r'(^(?:\s*' + MANA_SEARCH_REGEX + r')*)'
SANITIZATION_REPLACEMENTS = {
    'ʹʻʼʾˈ՚′＇ꞌ': '\'',  # apostrophes
    'ʻʼ‘’❛❜': '\'',  # quotes
    '“”″❞〝〞ˮ': '"',  # double quotes
}


def recipe(ingredients: list[str], results: list[str], negative_results: list[str] = []):
    return ' + '.join(ingredients) \
        + ' ➜ ' + ' + '.join(results[:3]) \
        + ('...' if len(results) > 3 else '') \
        + (' - ' + ' - '.join(negative_results[:3]) if negative_results else '') \
        + ('...' if len(negative_results) > 3 else '')


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def id_from_cards_and_templates_ids(cards: list[int], templates: list[int]) -> str:
    sorted_templates = sorted(templates)
    return '-'.join(str(c) for c in sorted(cards)) + ('--' + '--'.join(str(t) for t in sorted_templates) if len(sorted_templates) > 0 else '')


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    i.discard('C')
    return ''.join([color for color in 'WUBRG' if color in i]) or 'C'


def mana_value(mana: str) -> int:
    value = 0
    mana_cut_match = re.search(MANA_PREFIX_REGEX, mana, flags=re.IGNORECASE)
    if mana_cut_match:
        mana_cut = mana_cut_match.group(0)
        for mana in re.findall(MANA_SEARCH_REGEX, mana_cut, flags=re.IGNORECASE):
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


def sanitize_apostrophes_and_quotes(s: str) -> str:
    for chars, replacement in SANITIZATION_REPLACEMENTS.items():
        for c in chars:
            s = s.replace(c, replacement)
    return s


def apply_recursively_to_strings(data: dict, func: Callable[[str], str]):
    for key, value in data.items():
        if isinstance(value, str):
            data[key] = func(value)
        elif isinstance(value, dict):
            apply_recursively_to_strings(value, func)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    value[i] = func(item)
                elif isinstance(item, dict):
                    apply_recursively_to_strings(item, func)
