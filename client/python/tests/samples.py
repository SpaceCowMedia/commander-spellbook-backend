'''Responses shaped like the backend's, built from the OpenAPI schema the client was generated from.

Every property of every object is filled, nullable ones included, so a sample reaches every nested model.
With unexpected_fields, every object also carries fields the schema does not declare, as a newer
backend would send them to an older client.
'''
import json
import re
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import Any, Sequence


SCHEMA_PATH = Path(__file__).resolve().parents[2] / 'openapi.json'

UNEXPECTED_FIELDS: dict[str, Any] = {
    'unexpectedString': 'unexpected',
    'unexpectedNumber': 42,
    'unexpectedBoolean': True,
    'unexpectedNull': None,
    'unexpectedArray': [1, 'two', {'three': 3}],
    'unexpectedObject': {'nested': {'deeper': ['value']}},
}

STRING_FORMATS = {
    'date': '2026-01-01',
    'date-time': '2026-01-01T00:00:00Z',
    'email': 'user@example.com',
    'uri': 'https://example.com/',
    'uuid': '00000000-0000-4000-8000-000000000000',
}

# tried in order, the first one satisfying the length and pattern constraints is used
STRING_CANDIDATES = ('Sample', 'example.com', '1', '')


@cache
def openapi_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))


def component_schemas() -> dict[str, dict[str, Any]]:
    return openapi_schema()['components']['schemas']


def object_schema_names() -> list[str]:
    return [name for name, schema in component_schemas().items() if schema.get('type') == 'object']


def resolve(schema: dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(schema, str):
        return component_schemas()[schema]
    if '$ref' in schema:
        return resolve(schema['$ref'].removeprefix('#/components/schemas/'))
    return schema


def sample(schema: dict[str, Any] | str, unexpected_fields: bool = False) -> Any:
    schema = resolve(schema)
    if 'allOf' in schema:
        parts = [sample(part, unexpected_fields) for part in schema['allOf']]
        if all(isinstance(part, dict) for part in parts):
            return {key: value for part in parts for key, value in part.items()}
        return parts[0]
    if 'enum' in schema:
        return schema['enum'][0]
    match schema.get('type'):
        case 'object':
            properties = schema.get('properties', {})
            result = {name: sample(property, unexpected_fields) for name, property in properties.items()}
            if unexpected_fields and properties:
                result.update(deepcopy(UNEXPECTED_FIELDS))
            return result
        case 'array':
            return [sample(schema['items'], unexpected_fields) for _ in range(max(1, schema.get('minItems', 0)))]
        case 'string':
            return sample_string(schema)
        case 'integer':
            return clamp(1, schema)
        case 'number':
            return clamp(1.5, schema)
        case 'boolean':
            return True
        case None:
            # an untyped schema, such as a JSON field, accepts any value
            return STRING_CANDIDATES[0]
    raise NotImplementedError(f'Cannot build a sample of {schema}')


def sample_string(schema: dict[str, Any]) -> str:
    if schema.get('format') in STRING_FORMATS:
        return STRING_FORMATS[schema['format']]
    for candidate in STRING_CANDIDATES:
        if len(candidate) < schema.get('minLength', 0) or len(candidate) > schema.get('maxLength', len(candidate)):
            continue
        if 'pattern' in schema and not re.search(schema['pattern'], candidate):
            continue
        return candidate
    raise NotImplementedError(f'No sample string satisfies {schema}')


def clamp(value: int | float, schema: dict[str, Any]) -> int | float:
    return min(max(value, schema.get('minimum', value)), schema.get('maximum', value))


def variant_sample(
    id: str = '1-2',
    cards: Sequence[str] = ('Card A', 'Card B'),
    templates: Sequence[str] = (),
    results: Sequence[str] = ('Result A',),
    identity: str = 'UB',
    popularity: int = 100,
    spoiler: bool = False,
    unexpected_fields: bool = True,
) -> dict[str, Any]:
    '''A variant using the given cards and templates to produce the given results.'''
    variant = sample('Variant', unexpected_fields)
    variant.update(id=id, identity=identity, popularity=popularity, spoiler=spoiler)
    variant['uses'] = [
        {**variant['uses'][0], 'card': {**variant['uses'][0]['card'], 'id': i, 'name': name}, 'quantity': 1}
        for i, name in enumerate(cards, start=1)
    ]
    variant['requires'] = [
        {**variant['requires'][0], 'template': {**variant['requires'][0]['template'], 'id': i, 'name': name}, 'quantity': 1}
        for i, name in enumerate(templates, start=1)
    ]
    variant['produces'] = [
        {**variant['produces'][0], 'feature': {**variant['produces'][0]['feature'], 'id': i, 'name': name}, 'quantity': 1}
        for i, name in enumerate(results, start=1)
    ]
    return variant


def paginated_sample(results: Any, count: int | None = None, unexpected_fields: bool = True) -> dict[str, Any]:
    '''A page of results, counting them unless told otherwise.'''
    page = {'count': len(results) if count is None else count, 'next': None, 'previous': None, 'results': results}
    if unexpected_fields:
        page.update(deepcopy(UNEXPECTED_FIELDS))
    return page
