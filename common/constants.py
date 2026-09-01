import os


SORTED_COLORS = {
    frozenset(i): i for i in (
        'C',
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
        'WUBRG',
    )
}
COLORS = frozenset('WUBRG')

VERSION = os.getenv('VERSION', 'dev')
USER_AGENT = f'CommanderSpellbook/{VERSION}'
API_URL = os.getenv('SPELLBOOK_API_URL', '')
WEBSITE_URL = os.getenv('SPELLBOOK_WEBSITE_URL', '')
FILES_URL = os.getenv('SPELLBOOK_FILES_URL', '')
VARIANTS_FILE_NAME = 'variants.json'
VARIANTS_GZIP_FILE_NAME = f'{VARIANTS_FILE_NAME}.gz'
BULK_VARIANTS_URL = f'{FILES_URL}/{VARIANTS_FILE_NAME}'
BULK_VARIANTS_GZIP_URL = f'{FILES_URL}/{VARIANTS_GZIP_FILE_NAME}'
