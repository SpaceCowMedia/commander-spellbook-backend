from spellbook.models.utils import SORTED_COLORS


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
