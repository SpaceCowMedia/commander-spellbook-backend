from constants import SORTED_COLORS


def parse_color(value: str) -> str | None:
    value = value.upper()
    value_set = frozenset(value)
    if value_set in SORTED_COLORS:
        return SORTED_COLORS[value_set]
    match value:
        case 'C' | 'COLORLESS':
            value_set = frozenset('C')
        case 'WHITE' | 'MONOWHITE':
            value_set = frozenset('W')
        case 'BLUE' | 'MONOBLUE':
            value_set = frozenset('U')
        case 'BLACK' | 'MONOBLACK':
            value_set = frozenset('B')
        case 'RED' | 'MONORED':
            value_set = frozenset('R')
        case 'GREEN' | 'MONOGREEN':
            value_set = frozenset('G')
        case 'AZORIUS':
            value_set = frozenset('WU')
        case 'DIMIR':
            value_set = frozenset('UB')
        case 'RAKDOS':
            value_set = frozenset('BR')
        case 'GRUUL':
            value_set = frozenset('RG')
        case 'SELESNYA':
            value_set = frozenset('WG')
        case 'ORZHOV':
            value_set = frozenset('WB')
        case 'IZZET':
            value_set = frozenset('UR')
        case 'GOLGARI':
            value_set = frozenset('BG')
        case 'BOROS':
            value_set = frozenset('WR')
        case 'SIMIC':
            value_set = frozenset('UG')
        case 'NAYA':
            value_set = frozenset('WRG')
        case 'ESPER':
            value_set = frozenset('WUB')
        case 'GRIXIS':
            value_set = frozenset('UBR')
        case 'JUND':
            value_set = frozenset('BRG')
        case 'BANT':
            value_set = frozenset('WUG')
        case 'ABZAN':
            value_set = frozenset('WBG')
        case 'TEMUR':
            value_set = frozenset('URG')
        case 'JESKAI':
            value_set = frozenset('WUR')
        case 'MARDU':
            value_set = frozenset('WBR')
        case 'SULTAI':
            value_set = frozenset('UBG')
        case 'CHAOS' | 'GLINT' | 'GLINTEYE' | 'SANSWHITE':
            value_set = frozenset('UBRG')
        case 'AGGRESSION' | 'DUNE' | 'DUNEBROOD' | 'SANSBLUE':
            value_set = frozenset('WBRG')
        case 'ALTRUISM' | 'INK' | 'INKTREADER' | 'SANSBLACK':
            value_set = frozenset('WURG')
        case 'GROWTH' | 'WITCH' | 'WITCHMAW' | 'SANSRED':
            value_set = frozenset('WUBG')
        case 'ARTIFICE' | 'YORE' | 'YORETILLER' | 'SANSGREEN':
            value_set = frozenset('WUBR')
        case '5COLOR' | '5COLORS' | 'FIVECOLOR' | 'FIVECOLORS' | 'PENTA' | 'PENTACOLOR':
            value_set = frozenset('WUBRG')
        case _:
            value_set = frozenset()
    if value_set in SORTED_COLORS:
        return SORTED_COLORS[value_set]
    return None


# the names Scryfall reads a produces search by, measured against it: fewer than a color search takes,
# since colorless, the mono and sans names and the short four-color ones are all refused there
PRODUCED_MANA_NAMES = {
    'white': 'w', 'blue': 'u', 'black': 'b', 'red': 'r', 'green': 'g',
    'azorius': 'wu', 'dimir': 'ub', 'rakdos': 'br', 'gruul': 'rg', 'selesnya': 'wg',
    'orzhov': 'wb', 'izzet': 'ur', 'golgari': 'bg', 'boros': 'wr', 'simic': 'ug',
    'silverquill': 'wb', 'prismari': 'ur', 'witherbloom': 'bg', 'lorehold': 'wr', 'quandrix': 'ug',
    'naya': 'wrg', 'esper': 'wub', 'grixis': 'ubr', 'jund': 'brg', 'bant': 'wug',
    'abzan': 'wbg', 'temur': 'urg', 'jeskai': 'wur', 'mardu': 'wbr', 'sultai': 'ubg',
    'chaos': 'ubrg', 'glinteye': 'ubrg', 'aggression': 'wbrg', 'dunebrood': 'wbrg', 'altruism': 'wurg',
    'inktreader': 'wurg', 'growth': 'wubg', 'witchmaw': 'wubg', 'artifice': 'wubr', 'yoretiller': 'wubr',
}

PRODUCED_MANA_COUNTS = {str(count): count for count in range(7)} | {'rainbow': 5, 'all': 6}

MULTICOLORED_PRODUCED_MANA = {
    ':': ('>=', 2), '=': ('>=', 2), '>=': ('>=', 2), '>': ('>=', 2), '<=': ('>=', 1), '<': ('=', 1), '!=': ('=', 1),
}

PRODUCED_MANA_KEYWORDS = {
    'm': MULTICOLORED_PRODUCED_MANA,
    'multi': MULTICOLORED_PRODUCED_MANA,
    'multicolor': MULTICOLORED_PRODUCED_MANA,
    'multicolour': MULTICOLORED_PRODUCED_MANA,
    'any': {':': ('>=', 1), '=': ('>=', 1), '>=': ('>=', 1), '>': ('>=', 1), '!=': ('>=', 1), '<=': ('<=', 1), '<': ('=', 0)},
}


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
    value = PRODUCED_MANA_NAMES.get(value, value)
    if value and set(value) <= set('wubrgc'):
        return operator, ''.join(kind for kind in 'WUBRGC' if kind.lower() in value)
    return None
