from typing import Any
from lark import Lark, LarkError, UnexpectedToken, UnexpectedCharacters
from django.core.exceptions import ValidationError
from django.db.models import F, Q, Value
from django.db.models.expressions import Combinable
from django.db.models.lookups import Exact, GreaterThan, GreaterThanOrEqual, LessThan, LessThanOrEqual, Lookup

MAX_QUERY_LENGTH = 1024
MAX_QUERY_PARAMETERS = 20

LOOKUPS: dict[str, type[Lookup]] = {
    ':': Exact,
    '=': Exact,
    '<': LessThan,
    '<=': LessThanOrEqual,
    '>': GreaterThan,
    '>=': GreaterThanOrEqual,
}


def expression(operand: Any) -> Combinable:
    '''A comparison operand as an expression: a string names a field, anything else is a literal.'''
    if isinstance(operand, Combinable):
        return operand
    return F(operand) if isinstance(operand, str) else Value(operand)


def compare(left: Any, operator: str, right: Any) -> Q:
    '''The condition the operator asks for between two operands, each a field name, a literal or an
    expression already.

    A column holding no number is null, and every comparison against null is null, which is what keeps
    a card printing a star for power out of an answer about power. The inequality is written as a
    negated comparison between expressions rather than as a filter on a field, because Django widens
    the latter with a null check of its own that would let that same card back in.'''
    if operator == '!=':
        return ~Q(Exact(expression(left), expression(right)))
    if operator in LOOKUPS:
        return Q(LOOKUPS[operator](expression(left), expression(right)))
    raise ValidationError(f'Operator {operator} is not supported for a comparison.')


def parse_query(parser: Lark, query_string: str) -> Any:
    '''Parses a search query with a parser whose transformer builds a tree that counts its own
    `leaves`, reporting anything that makes the query unusable as a ValidationError.'''
    query_string = query_string.strip()
    if len(query_string) > MAX_QUERY_LENGTH:
        raise ValidationError('Search query is too long.')
    try:
        query = parser.parse(query_string)
        if query.leaves > MAX_QUERY_PARAMETERS:  # type: ignore
            raise ValidationError('Too many search parameters.')
        return query
    except UnexpectedToken as e:
        if e.token.type == '$END':
            raise ValidationError(f'Invalid search query: something is missing after character {e.column}.')
        raise ValidationError(f'Invalid search query: something is wrong at character {e.column + 1}.')
    except UnexpectedCharacters as e:
        raise ValidationError(f'Invalid search query: unexpected character {query_string[e.column - 1]} at position {e.column}.')
    except LarkError as e:
        raise ValidationError(f'Invalid search query: {e}')
