from typing import Any


def mark_all_outputs_required(result: dict[str, dict[str, dict[str, dict[str, Any]]]], **kwargs: Any):
    schemas = result.get('components', {}).get('schemas', {})
    for name, schema in schemas.items():
        if name.endswith('Request') or name.endswith('Enum'):
            continue
        schema['required'] = sorted(schema['properties'].keys())
    return result
