import re
import os
from itertools import chain
from urllib.parse import quote_plus as encode_query, urlparse
from functools import cached_property
from anonymous_spellbook_client import AnonymousSpellbookClient
from spellbook_client.models.variant import Variant


WEBSITE_URL = os.getenv('SPELLBOOK_WEBSITE_URL', '')
API = AnonymousSpellbookClient(base_url=os.getenv('SPELLBOOK_API_URL', ''))

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


def url_from_query(query: str) -> str:
    return f'{WEBSITE_URL}/search?q={encode_query(patch_query(query))}'


def summary_from_query(query: str, query_url: str) -> str:
    return f'["`{query}`"]({query_url})'


def url_from_variant(variant: Variant) -> str:
    return f'{WEBSITE_URL}/combo/{variant.id}'


def compute_variant_name(variant: Variant):
    return ' + '.join(chain(
        ((f'{card.quantity}x ' if card.quantity > 1 else '') + card.card.name for card in variant.uses),
        ((f'{template.quantity}x ' if template.quantity > 1 else '') + template.template.name for template in variant.requires),
    ))


def compute_variant_recipe(variant: Variant):
    variant_name = compute_variant_name(variant)
    variant_results = ', '.join(result.feature.name for result in variant.produces[:4]) + ('...' if len(variant.produces) > 4 else '')
    return f'{variant_name} ➜ {variant_results}'


def compute_variant_results(variant: Variant):
    return '\n'.join(
        (f'{result.quantity}x ' if result.quantity > 1 else '') + result.feature.name
        for result in variant.produces
    )


def uri_validator(x: str):
    try:
        result = urlparse(x)
        return all([result.scheme, result.netloc])
    except AttributeError:
        return False



class SpellbookQuery:
    def __init__(self, query: str):
        self.query = query

    @cached_property
    def patched_query(self) -> str:
        return patch_query(self.query)

    @cached_property
    def url(self) -> str:
        return url_from_query(self.query)

    @cached_property
    def summary(self) -> str:
        return summary_from_query(self.query, self.url)
