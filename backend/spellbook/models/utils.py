import re
import unicodedata
from typing import Iterable, Sequence

from ..regexs import MANA_SYMBOL, ORACLE_SYMBOL, ORACLE_SYMBOL_EXTENDED
from ..parsers.scryfall_query_grammar import COMPARISON_OPERATORS, MANA_COMPARABLE_VARIABLES
from django.utils.text import normalize_newlines
from django.db.models import Expression, F, Value, TextChoices
from django.db.models.functions import Replace, Trim


COMPARISON_OPERATOR = rf'(?:{"|".join(COMPARISON_OPERATORS)})'
MANA_SEARCH_REGEX = r'\{(' + MANA_SYMBOL + r')\}'
MANA_PREFIX_REGEX = r'(^(?:\s*' + MANA_SEARCH_REGEX + r')*)'
MANA_COMPARABLE_VARIABLE = rf'(?:{"|".join(MANA_COMPARABLE_VARIABLES)})'
SANITIZATION_REPLACEMENTS = {
    'ʹʻʼʾˈ՚′＇ꞌ': '\'',  # apostrophes
    'ʻʼ‘’❛❜': '\'',  # quotes
    '“”″❞〝〞ˮ': '"',  # double quotes
}
SORTED_COLORS = {
    frozenset('C'): 'C',
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
        + (' - ' + ' - '.join(negative_results[:3]) if negative_results else '') \
        + ('...' if len(negative_results) > 3 else '')


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def id_from_cards_and_templates_ids(cards: Iterable[int], templates: Iterable[int]) -> str:
    sorted_templates = sorted(templates)
    return '-'.join(str(c) for c in sorted(cards)) + ('--' + '--'.join(str(t) for t in sorted_templates) if len(sorted_templates) > 0 else '')


def sort_color_identity(identity_set: frozenset[str]) -> str:
    return SORTED_COLORS[identity_set or frozenset('C')]


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


def auto_fix_reverse_hybrid_mana(text: str):
    def replace_reversed(text: str, color_combo: str):
        return re.sub(r'\{' + '/'.join(reversed(color_combo)) + r'\}', r'{' + '/'.join(color_combo) + r'}', text, flags=re.IGNORECASE)
    for color_combo in SORTED_COLORS.values():
        match len(color_combo):
            case 1:
                text = replace_reversed(text, f'2{color_combo}')
                text = replace_reversed(text, f'{color_combo}P')
            case 2:
                text = replace_reversed(text, color_combo)
    return text


def auto_fix_missing_braces_to_oracle_symbols(text: str):
    if re.compile(r'^' + ORACLE_SYMBOL_EXTENDED + r'+$', flags=re.IGNORECASE).match(text):
        return re.sub(r'\{?(' + ORACLE_SYMBOL_EXTENDED + r')\}?', r'{\1}', text, flags=re.IGNORECASE)
    return text


def sanitize_mana(mana: str) -> str:
    mana = auto_fix_missing_braces_to_oracle_symbols(mana)
    mana = auto_fix_reverse_hybrid_mana(mana)
    mana = re.sub(r'\{([WUBRG])P\}', r'{\1/P}', mana, flags=re.IGNORECASE)
    mana = upper_oracle_symbols(mana)
    return mana


def sanitize_scryfall_query(text: str):
    text = re.sub(r'(?:^|\s+)-?(?:f|format|legal):[^\s]+(?=\s|$)', '', text, flags=re.IGNORECASE)
    text = text.strip()
    text = re.sub(rf'(^|\s+)(-?{MANA_COMPARABLE_VARIABLE})({COMPARISON_OPERATOR})([^\s]+)(?=\s|$)', lambda m: f'{m[1]}{m[2]}{m[3]}{sanitize_mana(m[4])}', text, flags=re.IGNORECASE)
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


def chain_strings(strings: Sequence[str]) -> str:
    if not strings:
        return ''
    if len(strings) <= 2:
        return ' and '.join(strings)
    return ', '.join(strings[:-1]) + ', and ' + strings[-1]
