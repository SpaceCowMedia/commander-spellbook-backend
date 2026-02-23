from pathlib import Path
from spellbook.models import Variant


SUPPORTED_STORES = {s.removeprefix('price_') for s in Variant.prices_fields()}


with open(Path(__file__).parent / 'variants_query_grammar.lark', 'r') as f:
    VARIANTS_QUERY_GRAMMAR = f.read() + f'''
        SUPPORTED_STORE : {' | '.join(f'"{s}"i' for s in SUPPORTED_STORES)}
    '''
