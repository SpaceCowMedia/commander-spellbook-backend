import re
import unicodedata
from typing import Iterable
from .validators import MANA_SYMBOL, ORACLE_SYMBOL, COMPARISON_OPERATORS, MANA_COMPARABLE_VARIABLE
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
    frozenset[str](): 'C',
    **{frozenset(i): i for i in [
        'W',
        'U',
        'B',
        'R',
        'G',
        'WU',
        'WB',
        'RW',
        'GW',
        'UB',
        'UR',
        'GU',
        'BR',
        'BG',
        'RG',
        'WUB',
        'URW',
        'GWU',
        'RWB',
        'WBG',
        'RGW',
        'UBR',
        'BGU',
        'GUR',
        'BRG',
        'WUBR',
        'UBRG',
        'BRGW',
        'RGWU',
        'GWUB',
        'WUBRG'
    ]}
}


def recipe(ingredients: list[str], results: list[str], negative_results: list[str] = []):
    return ' + '.join(ingredients) \
        + ' ➜ ' + ' + '.join(results[:3]) \
        + ('...' if len(results) > 3 else '') \
        + (' - ' + ' - '.join(negative_results[:3]) if negative_results else '') \
        + ('...' if len(negative_results) > 3 else '')


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def id_from_cards_and_templates_ids(cards: Iterable[int], templates: Iterable[int]) -> str:
    sorted_templates = sorted(templates)
    return '-'.join(str(c) for c in sorted(cards)) + ('--' + '--'.join(str(t) for t in sorted_templates) if len(sorted_templates) > 0 else '')


def sort_color_identity(identity_set: frozenset[str]) -> str:
    return SORTED_COLORS[identity_set]


def merge_identities(identities: Iterable[str]) -> str:
    identity_set = frozenset(''.join(identities).upper()).intersection('WUBRG')
    return sort_color_identity(identity_set)


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


def upper_oracle_symbols(text: str):
    return re.sub(r'\{' + ORACLE_SYMBOL + r'\}', lambda m: m.group(0).upper(), text, flags=re.IGNORECASE)


def auto_fix_missing_braces_to_oracle_symbols(text: str):
    if re.compile(r'^' + ORACLE_SYMBOL + r'+$', flags=re.IGNORECASE).match(text):
        return re.sub(r'\{?(' + ORACLE_SYMBOL + r')\}?', r'{\1}', text, flags=re.IGNORECASE)
    return text


def sanitize_mana(mana: str) -> str:
    mana = auto_fix_missing_braces_to_oracle_symbols(mana)
    mana = re.sub(r'\{([WUBRG])P\}', r'{\1/P}', mana, flags=re.IGNORECASE)
    mana = upper_oracle_symbols(mana)
    return mana


def sanitize_scryfall_query(text: str):
    text = re.sub(r'(?:^|\s+)-?(?:f|format|legal):[^\s]+(?=\s|$)', '', text, flags=re.IGNORECASE)
    text = text.strip()
    text = re.sub(rf'(^|\s+)(-?{MANA_COMPARABLE_VARIABLE})({COMPARISON_OPERATORS})([^\s]+)(?=\s|$)', lambda m: f'{m[1]}{m[2]}{m[3]}{sanitize_mana(m[4])}', text, flags=re.IGNORECASE)
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
