from pathlib import Path
from spellbook.models import Variant


with open(Path(__file__).parent / 'variants_query_grammar.lark', 'r') as f:
    VARIANTS_QUERY_GRAMMAR = f.read() + f'''
        SUPPORTED_STORE : {' | '.join(f'"{s.removeprefix('price_')}"i' for s in Variant.prices_fields())}
    '''
