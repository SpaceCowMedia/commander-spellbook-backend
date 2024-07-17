from lark import Lark
from pathlib import Path
from ..regexs import MANA_SYMBOL


# Scryfall query syntax: https://scryfall.com/docs/syntax
COMPARISON_OPERATORS = ['=', '!=', '<', '>', '<=', '>=', ':']
NUMERIC_VARIABLES = ['mv', 'manavalue', 'power', 'pow', 'toughness', 'tou', 'pt', 'powtou', 'loyalty', 'loy']
STRING_COMPARABLE_VARIABLES = ['c', 'color', 'id', 'identity', 'produces']
STRING_UNCOMPARABLE_VARIABLES = ['has', 't', 'type', 'keyword', 'kw', 'is', 'o', 'oracle', 'function', 'otag', 'oracletag', 'oracleid']
MANA_COMPARABLE_VARIABLES = ['m', 'mana', 'devotion']

VARIABLES_SUPPORTED = [
    *NUMERIC_VARIABLES,
    *STRING_COMPARABLE_VARIABLES,
    *STRING_UNCOMPARABLE_VARIABLES,
    *MANA_COMPARABLE_VARIABLES,
]

with open(Path(__file__).parent / 'scryfall_query_grammar.lark', 'r') as f:
    grammar = f.read() + f'''
        MANA_SYMBOL.5 : /\\{{{MANA_SYMBOL}\\}}/
        COMPARISON_OPERATOR : {' | '.join(f'"{v}"' for v in COMPARISON_OPERATORS)}
        NUMERIC_VARIABLE.4 : {' | '.join(f'"{v}"' for v in NUMERIC_VARIABLES)}
        MANA_VARIABLE.3 : {' | '.join(f'"{v}"' for v in MANA_COMPARABLE_VARIABLES)}
        COMPARABLE_STRING_VARIABLE.2 : {' | '.join(f'"{v}"' for v in STRING_COMPARABLE_VARIABLES)}
        UNCOMPARABLE_STRING_VARIABLE.1 : {' | '.join(f'"{v}"' for v in STRING_UNCOMPARABLE_VARIABLES)}
    '''
    SCRYFALL_PARSER = Lark(grammar, parser='lalr')
