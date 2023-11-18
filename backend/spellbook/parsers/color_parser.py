def parse_identity(value: str) -> str | None:
    value = value.upper()
    all_colors = 'WUBRG'
    value_set = set(value)
    if value_set.issubset(all_colors):
        return ''.join(c for c in all_colors if c in value)
    match value:
        case 'C' | 'COLORLESS':
            return 'C'
        case 'WHITE' | 'MONOWHITE':
            return 'W'
        case 'BLUE' | 'MONOBLUE':
            return 'U'
        case 'BLACK' | 'MONOBLACK':
            return 'B'
        case 'RED' | 'MONORED':
            return 'R'
        case 'GREEN' | 'MONOGREEN':
            return 'G'
        case 'AZORIUS':
            return 'WU'
        case 'DIMIR':
            return 'UB'
        case 'RAKDOS':
            return 'BR'
        case 'GRUUL':
            return 'RG'
        case 'SELESNYA':
            return 'WG'
        case 'ORZHOV':
            return 'WB'
        case 'IZZET':
            return 'UR'
        case 'GOLGARI':
            return 'BG'
        case 'BOROS':
            return 'WR'
        case 'SIMIC':
            return 'UG'
        case 'NAYA':
            return 'WRG'
        case 'ESPER':
            return 'WUB'
        case 'GRIXIS':
            return 'UBR'
        case 'JUND':
            return 'BRG'
        case 'BANT':
            return 'WUG'
        case 'ABZAN':
            return 'WBG'
        case 'TEMUR':
            return 'URG'
        case 'JESKAI':
            return 'WUR'
        case 'MARDU':
            return 'WBR'
        case 'SULTAI':
            return 'UBG'
        case 'CHAOS' | 'GLINT' | 'GLINTEYE' | 'SANSWHITE':
            return 'UBRG'
        case 'AGGRESSION' | 'DUNE' | 'DUNEBROOD' | 'SANSBLUE':
            return 'WBRG'
        case 'ALTRUISM' | 'INK' | 'INKTREADER' | 'SANSBLACK':
            return 'WURG'
        case 'GROWTH' | 'WITCH' | 'WITCHMAW' | 'SANSRED':
            return 'WUBG'
        case 'ARTIFICE' | 'YORE' | 'YORETILLER' | 'SANSGREEN':
            return 'WUBR'
        case '5COLOR' | '5COLORS' | 'FIVECOLOR' | 'FIVECOLORS' | 'PENTA' | 'PENTACOLOR':
            return 'WUBRG'
        case _:
            return None
