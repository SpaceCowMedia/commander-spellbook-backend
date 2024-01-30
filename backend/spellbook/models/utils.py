import re
import unicodedata
from typing import Iterable, Callable
from .validators import MANA_SYMBOL
from django.utils.text import normalize_newlines
from django.db.models import Expression, F, Value
from django.db.models.functions import Replace, Trim


MANA_SEARCH_REGEX = r'\{(' + MANA_SYMBOL + r')\}'
MANA_PREFIX_REGEX = r'(^(?:\s*' + MANA_SEARCH_REGEX + r')*)'
SANITIZATION_REPLACEMENTS = {
    'ʹʻʼʾˈ՚′＇ꞌ': '\'',  # apostrophes
    'ʻʼ‘’❛❜': '\'',  # quotes
    '“”″❞〝〞ˮ': '"',  # double quotes
}
SORTED_COLORS = {
    frozenset({}): "C",
    frozenset({"W"}): "W",
    frozenset({"U"}): "U",
    frozenset({"B"}): "B",
    frozenset({"R"}): "R",
    frozenset({"G"}): "G",
    frozenset({"W", "U"}): "WU",
    frozenset({"W", "B"}): "WB",
    frozenset({"W", "R"}): "RW",
    frozenset({"W", "G"}): "GW",
    frozenset({"U", "B"}): "UB",
    frozenset({"U", "R"}): "UR",
    frozenset({"U", "G"}): "GU",
    frozenset({"B", "R"}): "BR",
    frozenset({"B", "G"}): "BG",
    frozenset({"R", "G"}): "RG",
    frozenset({"W", "U", "B"}): "WUB",
    frozenset({"W", "U", "R"}): "URW",
    frozenset({"W", "U", "G"}): "GWU",
    frozenset({"W", "B", "R"}): "RWB",
    frozenset({"W", "B", "G"}): "WBG",
    frozenset({"W", "R", "G"}): "RGW",
    frozenset({"U", "B", "R"}): "UBR",
    frozenset({"U", "B", "G"}): "BGU",
    frozenset({"U", "R", "G"}): "GUR",
    frozenset({"B", "R", "G"}): "BRG",
    frozenset({"W", "U", "B", "R"}): "WUBR",
    frozenset({"U", "B", "R", "G"}): "UBRG",
    frozenset({"B", "R", "G", "W"}): "BRGW",
    frozenset({"R", "G", "W", "U"}): "RGWU",
    frozenset({"G", "W", "U", "B"}): "GWUB",
    frozenset({"W", "U", "B", "R", "G"}): "WUBRG"
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


def order_mana_identity(identity_set: frozenset[str]) -> str:
    return SORTED_COLORS[identity_set]


def merge_identities(identities: Iterable[str]) -> str:
    identity_set = frozenset(''.join(identities).upper()) - frozenset('C')
    return order_mana_identity(identity_set)


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


def sanitize_newlines_apostrophes_and_quotes(s: str) -> str:
    s = normalize_newlines(s)
    for chars, replacement in SANITIZATION_REPLACEMENTS.items():
        for c in chars:
            s = s.replace(c, replacement)
    return s


def apply_recursively_to_strings(data: dict | list, func: Callable[[str], str]) -> None:
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                data[key] = func(value)
            else:
                apply_recursively_to_strings(value, func)
    elif isinstance(data, list):
        for i, value in enumerate(data):
            if isinstance(value, str):
                data[i] = func(value)
            else:
                apply_recursively_to_strings(value, func)


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
