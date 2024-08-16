import re

QUERY_REGEX = re.compile(r'{{(.*?)}}')


def parse_queries(text: str) -> list[str]:
    result = []
    for match in QUERY_REGEX.finditer(text):
        query = match.group(1).strip()
        if query:
            result.append(query)
    return result


def patch_query(query: str) -> str:
    patched_query = query
    if not any(f'{key}:' in patched_query for key in ('legal', 'banned', 'format')):
        patched_query += ' format:commander'
    return patched_query
