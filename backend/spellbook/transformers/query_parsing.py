from typing import Any
from lark import Lark, LarkError, UnexpectedToken, UnexpectedCharacters
from django.core.exceptions import ValidationError

MAX_QUERY_LENGTH = 1024
MAX_QUERY_PARAMETERS = 20


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
