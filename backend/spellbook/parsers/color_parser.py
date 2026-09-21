from constants import SORTED_COLORS

# the names Scryfall reads a color by, measured against it, followed by the ones this search took on its
# own before, which Scryfall refuses
COLOR_NAMES = {
    'colorless': 'C', 'colourless': 'C',
    'white': 'W', 'blue': 'U', 'black': 'B', 'red': 'R', 'green': 'G',
    'azorius': 'WU', 'dimir': 'UB', 'rakdos': 'BR', 'gruul': 'RG', 'selesnya': 'GW',
    'orzhov': 'WB', 'izzet': 'UR', 'golgari': 'BG', 'boros': 'RW', 'simic': 'GU',
    'silverquill': 'WB', 'prismari': 'UR', 'witherbloom': 'BG', 'lorehold': 'RW', 'quandrix': 'GU',
    'bant': 'GWU', 'esper': 'WUB', 'grixis': 'UBR', 'jund': 'BRG', 'naya': 'RGW',
    'abzan': 'WBG', 'jeskai': 'URW', 'sultai': 'BGU', 'mardu': 'RWB', 'temur': 'GUR',
    'brokers': 'GWU', 'obscura': 'WUB', 'maestros': 'UBR', 'riveteers': 'BRG', 'cabaretti': 'RGW',
    'chaos': 'UBRG', 'glinteye': 'UBRG', 'glint-eye': 'UBRG',
    'aggression': 'BRGW', 'dunebrood': 'BRGW', 'dune-brood': 'BRGW',
    'altruism': 'RGWU', 'inktreader': 'RGWU', 'ink-treader': 'RGWU',
    'growth': 'GWUB', 'witchmaw': 'GWUB', 'witch-maw': 'GWUB',
    'artifice': 'WUBR', 'yoretiller': 'WUBR', 'yore-tiller': 'WUBR',
    'monowhite': 'W', 'monoblue': 'U', 'monoblack': 'B', 'monored': 'R', 'monogreen': 'G',
    'glint': 'UBRG', 'dune': 'BRGW', 'ink': 'RGWU', 'witch': 'GWUB', 'yore': 'WUBR',
    'sanswhite': 'UBRG', 'sansblue': 'BRGW', 'sansblack': 'RGWU', 'sansred': 'GWUB', 'sansgreen': 'WUBR',
    '5color': 'WUBRG', '5colors': 'WUBRG', 'fivecolor': 'WUBRG', 'fivecolors': 'WUBRG',
    'penta': 'WUBRG', 'pentacolor': 'WUBRG',
}


def parse_color(value: str) -> str | None:
    '''The colors a value names, either by their letters or by a name, in their canonical order.'''
    return SORTED_COLORS.get(frozenset(COLOR_NAMES.get(value.lower(), value.upper())))


MULTICOLORED_NAMES = ('m', 'multi', 'multicolor', 'multicolour')

COLOR_COUNTS = {str(count): count for count in range(6)} | {'rainbow': 5, 'all': 5}

MULTICOLORED_COLORS = {
    ':': ('>=', 2), '=': ('>=', 2), '>=': ('>=', 2), '>': ('>=', 2), '<=': ('>=', 0), '<': ('<=', 1), '!=': ('<=', 1),
}

PRODUCED_MANA_COUNTS = {str(count): count for count in range(7)} | {'rainbow': 5, 'all': 6}

MULTICOLORED_PRODUCED_MANA = {
    ':': ('>=', 2), '=': ('>=', 2), '>=': ('>=', 2), '>': ('>=', 2), '<=': ('>=', 1), '<': ('=', 1), '!=': ('=', 1),
}

PRODUCED_MANA_KEYWORDS = {name: MULTICOLORED_PRODUCED_MANA for name in MULTICOLORED_NAMES} | {
    'any': {':': ('>=', 1), '=': ('>=', 1), '>=': ('>=', 1), '>': ('>=', 1), '!=': ('>=', 1), '<=': ('<=', 1), '<': ('=', 0)},
}


def parse_colors(value: str, operator: str) -> tuple[str, str | int] | None:
    '''A color or identity search the way Scryfall reads it, as one comparison: of a card's colors to the
    ones named, colorless naming none of them, or of how many colors it has to a number.

    A colon asks for a number exactly, and the multicolored keyword stands for a number of colors that
    changes with the operator, the way Scryfall answers both.'''
    value = value.lower()
    if value in MULTICOLORED_NAMES:
        return MULTICOLORED_COLORS[operator]
    if value in COLOR_COUNTS:
        return ('=' if operator == ':' else operator), COLOR_COUNTS[value]
    parsed = parse_color(value)
    if parsed is None:
        return None
    return operator, parsed.replace('C', '')


def parse_produced_mana(value: str, operator: str) -> tuple[str, str | int] | None:
    '''A produces search the way Scryfall reads it, as one comparison: of the kinds of mana a card makes
    to the kinds named, colorless being one kind and not the absence of any, or of how many kinds it
    makes to a number.

    A keyword stands for a number of kinds that changes with the operator, and asking for fewer than
    zero kinds, or for any number but zero, gets the cards making none: neither is what the operator
    suggests, but both are what Scryfall answers.'''
    value = value.lower()
    if value in PRODUCED_MANA_KEYWORDS:
        return PRODUCED_MANA_KEYWORDS[value][operator]
    if value in PRODUCED_MANA_COUNTS:
        count = PRODUCED_MANA_COUNTS[value]
        return ('=', 0) if count == 0 and operator in ('<', '!=') else (operator, count)
    kinds = COLOR_NAMES.get(value, value.upper())
    if kinds and set(kinds) <= set('WUBRGC'):
        return operator, ''.join(kind for kind in 'WUBRGC' if kind in kinds)
    return None
