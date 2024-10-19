import json
from urllib.request import Request, urlopen
from spellbook.models import Variant


def edhrec():
    # Old ID -> new ID mapping fetching
    req = Request(
        'https://json.commanderspellbook.com/variant_id_map.json'
    )
    variants_id_map = dict[str, str]()
    with urlopen(req) as response:
        variants_id_map: dict[str, str] = json.loads(response.read().decode())
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


def update_variants(variants: list[Variant], counts: dict[str, int], edhrec: dict[str, dict], log=lambda t: print(t), log_warning=lambda t: print(t), log_error=lambda t: print(t)):
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
        requires_commander = any(civ.must_be_commander for civ in variant.cardinvariant_set.all()) \
            or any(tiv.must_be_commander for tiv in variant.templateinvariant_set.all())
        if variant.update(variant.uses.all(), requires_commander):
            updated = True
        # Update with Spellbook data
        variant_count = counts.get(variant.id, 0)
        if variant.variant_count != variant_count:
            variant.variant_count = variant_count
            updated = True
        # Save if updated
        if updated:
            variants_to_save.append(variant)
    return variants_to_save
