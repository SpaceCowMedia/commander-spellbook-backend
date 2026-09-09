from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.db.models import F, IntegerField, Q, Value
from django.db.models.functions import Cast, Length, Replace
from django.db.models.lookups import Exact, GreaterThan, GreaterThanOrEqual, LessThan, LessThanOrEqual


@dataclass(frozen=True)
class ScryfallValue:
    '''One `key operator value` term of a Scryfall query, with the value already unwrapped.'''
    key: str
    operator: str
    value: str
    quoted: bool = False
    regex: bool = False

    @classmethod
    def from_tokens(cls, key: str, operator: str, value: str) -> 'ScryfallValue':
        quoted = value.startswith('"') and value.endswith('"')
        regex = value.startswith('/') and value.endswith('/')
        if quoted or regex:
            value = value[1:-1]
        return cls(key.lower(), operator, value, quoted, regex)

    def unsupported(self) -> ValidationError:
        return ValidationError(f'Operator {self.operator} is not supported for {self.key} search.')


def symbol_count(symbol: str):
    '''How many times the mana symbol appears in the mana cost.'''
    return Cast(
        (Length('mana_cost') - Length(Replace(F('mana_cost'), Value(symbol), Value('')))) / len(symbol),
        IntegerField(),
    )


def total_symbol_count():
    '''How many mana symbols the mana cost is made of, counted by their opening brace.'''
    return Cast(Length('mana_cost') - Length(Replace(F('mana_cost'), Value('{'), Value(''))), IntegerField())


def mana_filter(symbols: list[str], operator: str) -> Q:
    '''The cost compared to the queried symbols as one multiset to another.

    Containment is a count per distinct symbol; a subset also has to account for the symbols the query
    does not name at all, which is why it asks the counts it does name to add up to the whole cost.'''
    counts = {symbol: symbols.count(symbol) for symbol in set(symbols)}
    total = len(symbols)
    if operator in (':', '>=', '>'):
        # a cost of zero demands nothing, so asking for at least it asks for nothing: mana>=0 is how a
        # query says any cost at all, while mana={0} still means the cost printed on Ornithopter
        counts = {symbol: count for symbol, count in counts.items() if symbol != '{0}'}
    named = sum((symbol_count(symbol) for symbol in counts), start=Value(0))
    match operator:
        case ':' | '>=':
            return Q(*(GreaterThanOrEqual(symbol_count(symbol), Value(count)) for symbol, count in counts.items()))
        case '>':
            return Q(*(GreaterThanOrEqual(symbol_count(symbol), Value(count)) for symbol, count in counts.items())) \
                & Q(GreaterThan(total_symbol_count(), Value(total)))
        case '=':
            return Q(*(Exact(symbol_count(symbol), Value(count)) for symbol, count in counts.items())) \
                & Q(Exact(total_symbol_count(), Value(total)))
        case '<=':
            return Q(*(LessThanOrEqual(symbol_count(symbol), Value(count)) for symbol, count in counts.items())) \
                & Q(Exact(named, total_symbol_count()))
        case '<':
            return Q(*(LessThanOrEqual(symbol_count(symbol), Value(count)) for symbol, count in counts.items())) \
                & Q(Exact(named, total_symbol_count())) \
                & Q(LessThan(total_symbol_count(), Value(total)))
        case '!=':
            return ~mana_filter(symbols, '=')
        case _:
            raise ValidationError(f'Operator {operator} is not supported for a mana cost.')
