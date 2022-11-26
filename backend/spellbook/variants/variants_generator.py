import json
import hashlib
import logging
from typing import Iterable
from dataclasses import dataclass
from django.db import transaction
from ..models import Job, Variant
from .variant_data import Data, debug_queries
from .combo_graph import Graph


@dataclass
class VariantDefinition:
    card_ids: list[int]
    template_ids: list[int]
    of_ids: set[int]
    feature_ids: set[int]
    included_ids: set[int]


def unique_id_from_cards_and_templates_ids(cards: list[int], templates: list[int]) -> str:
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(json.dumps({'c': sorted(cards), 't': sorted(templates)}).encode('utf-8'))
    return hash_algorithm.hexdigest()


def subtract_removed_features(variant: Variant, features: set[int]) -> set[int]:
    return features - set(variant.includes.values_list('removes__id', flat=True))


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    return ''.join([color for color in 'WUBRG' if color in i])


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False


def update_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition,
        status: Variant.Status,
        restore=False):
    variant = data.uid_to_variant[unique_id]
    variant.of.set(variant_def.of_ids)
    variant.includes.set(variant_def.included_ids)
    variant.produces.set(subtract_removed_features(variant, variant_def.feature_ids) - data.utility_features_ids)
    variant.identity = merge_identities(variant.uses.values_list('identity', flat=True))
    ok = status == Variant.Status.OK or \
        status != Variant.Status.NOT_WORKING and not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    if restore:
        combos = data.combos.filter(id__in=variant_def.included_ids)
        variant.zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
        variant.cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
        variant.other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
        variant.mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
        variant.description = '\n'.join(c.description for c in combos if len(c.description) > 0)
        variant.status = Variant.Status.NEW if ok else Variant.Status.NOT_WORKING
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    if not ok or restore:
        variant.save()
    return variant.id


def create_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition):
    combos = data.combos.filter(id__in=variant_def.included_ids)
    zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
    cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
    other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
    mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
    description = '\n'.join(c.description for c in combos if len(c.description) > 0)
    ok = not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    variant = Variant(
        unique_id=unique_id,
        zone_locations=zone_locations,
        cards_state=cards_state,
        other_prerequisites=other_prerequisites,
        mana_needed=mana_needed,
        description=description,
        identity=merge_identities(data.cards.filter(id__in=variant_def.card_ids).values_list('identity', flat=True)))
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    variant.save()
    variant.uses.set(variant_def.card_ids)
    variant.requires.set(variant_def.template_ids)
    variant.of.set(variant_def.of_ids)
    variant.includes.set(variant_def.included_ids)
    variant.produces.set(subtract_removed_features(variant, variant_def.feature_ids) - data.utility_features_ids)
    return variant.id


def get_variants_from_graph(data: Data, job: Job = None) -> dict[str, VariantDefinition]:
    logging.info('Computing all possible variants:')
    combos = list(data.combos.filter(generator=True))
    result = dict[str, VariantDefinition]()
    graph = Graph(data)
    total = len(combos)
    for i, combo in enumerate(combos):
        variants = graph.variants(combo.id)
        for variant in variants:
            cards_ids = [c.id for c in variant.cards]
            templates_ids = [t.id for t in variant.templates]
            unique_id = unique_id_from_cards_and_templates_ids(cards_ids, templates_ids)
            feature_ids = set(f.id for f in variant.features)
            combo_ids = set(c.id for c in variant.combos)
            if unique_id in result:
                x = result[unique_id]
                x.of_ids.add(combo.id)
                x.included_ids.update(combo_ids)
                x.feature_ids.update(feature_ids)
            else:
                logging.debug(f'Found new variant for combo {combo.id} ({i + 1}/{total}): {unique_id}')
                result[unique_id] = VariantDefinition(
                    card_ids=cards_ids,
                    template_ids=templates_ids,
                    feature_ids=feature_ids,
                    included_ids=combo_ids,
                    of_ids={combo.id})
        msg = f'{i + 1}/{total} combos processed (just processed combo {combo.id})'
        logging.info(msg)
        if job:
            with transaction.atomic(durable=True):
                job.message += msg + '\n'
                job.save()
    return result


def generate_variants(job: Job = None) -> tuple[int, int, int]:
    logging.info('Fetching variants set to RESTORE...')
    data = Data()
    to_restore = set(k for k, v in data.uid_to_variant.items() if v.status == Variant.Status.RESTORE)
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.uid_to_variant.keys())
    logging.info('Computing combos MILP representation...')
    variants = get_variants_from_graph(data, job)
    logging.info(f'Saving {len(variants)} variants...')
    if job:
        with transaction.atomic(durable=True):
            job.message += f'Saving {len(variants)} variants...\n'
            job.save()
    variants_ids = set()
    with transaction.atomic():
        for unique_id, variant_def in variants.items():
            if unique_id in old_id_set:
                status = data.uid_to_variant[unique_id].status
                update_variant(
                    data=data,
                    unique_id=unique_id,
                    variant_def=variant_def,
                    status=status,
                    restore=unique_id in to_restore)
            else:
                variants_ids.add(
                    create_variant(
                        data=data,
                        unique_id=unique_id,
                        variant_def=variant_def))
            debug_queries(True) # TODO too many queries
        if job is not None:
            job.variants.set(variants_ids)
        new_id_set = set(variants.keys())
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        restored = new_id_set & to_restore
        logging.info(f'Added {len(added)} new variants.')
        logging.info(f'Updated {len(restored)} variants.')
        delete_query = data.variants.filter(unique_id__in=to_delete, frozen=False)
        deleted = delete_query.count()
        delete_query.delete()
        logging.info(f'Deleted {deleted} variants...')
        logging.info('Done.')
        debug_queries(True)
        return len(added), len(restored), deleted
