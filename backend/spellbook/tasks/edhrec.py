import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from constants import FILES_URL
from spellbook.models import Variant


def edhrec():
    # Old ID -> new ID mapping fetching
    variants_id_map = dict[str, str]()
    if FILES_URL:
        req = Request(
            f'{FILES_URL}/variant_id_map.json'
        )
        try:
            with urlopen(req) as response:
                variants_id_map = json.loads(response.read().decode())
        except HTTPError as e:
            # S3 answers 403 for a missing object when listing is not allowed
            if e.code not in (403, 404):
                raise
    # EDHREC popularity database fetching
    req = Request(
        'https://edhrec.com/data/spellbook_counts.json'
    )
    variants_db = dict[str, dict]()
    with urlopen(req) as response:
        data = json.loads(response.read().decode())
        for variant_id, variant_data in data['combos'].items():
            if variant_id in variants_id_map:
                variant_id = variants_id_map[variant_id]
            if variant_id not in variants_db:
                variants_db[variant_id] = {
                    'popularity': variant_data['count'],
                }
            else:
                raise Exception(f'Variant {variant_id} has multiple entries in EDHREC data')
        for variant_id in data['errors'].keys():
            if variant_id in variants_id_map:
                variant_id = variants_id_map[variant_id]
            if variant_id not in variants_db:
                variants_db[variant_id] = {
                    'popularity': 0,
                }
            else:
                raise Exception(f'Variant {variant_id} has multiple entries in EDHREC data')
    return variants_db


def update_variants(variants: list[Variant], edhrec: dict[str, dict]):
    variants_to_save: list[Variant] = []
    for variant in variants:
        updated = False
        # Update with EDHREC data
        if variant.id in edhrec:
            variant_data = edhrec[variant.id]
            if variant.popularity != variant_data['popularity']:
                variant.popularity = variant_data['popularity']
                updated = True
        elif variant.popularity is not None:
            variant.popularity = None
            updated = True
        # Update with card data
        if variant.update_variant():
            updated = True
        # Save if updated
        if updated:
            variants_to_save.append(variant)
    return variants_to_save
