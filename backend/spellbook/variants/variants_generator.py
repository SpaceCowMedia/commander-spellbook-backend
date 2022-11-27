import json
import hashlib
import logging
from typing import Iterable
from dataclasses import dataclass
from django.db import transaction
from ..models import Job, Variant
from .variant_data import Data, debug_queries
from .combo_graph import Graph


def log_into_job(job: Job, message: str, reset=False):
    if job:
        if reset:
            job.message = message
        else:
            job.message += message + '\n'
        with transaction.atomic(durable=True):
            job.save()


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


def subtract_removed_features(data: Data, includes: set[int], features: set[int]) -> set[int]:
    return features - set(r for c in includes for r in data.combo_to_removed_features[c])


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    return ''.join([color for color in 'WUBRG' if color in i])


def includes_any(v: set[int], others: Iterable[set[int]]) -> bool:
    for o in others:
        if v.issuperset(o):
            return True
    return False


@dataclass
class VariantBulkSaveItem:
    should_save: bool
    variant: Variant
    uses: list[int] | None
    requires: list[int] | None
    of: set[int]
    includes: set[int]
    produces: set[int]


def update_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition,
        status: Variant.Status,
        restore=False):
    variant = data.uid_to_variant[unique_id]
    ok = status == Variant.Status.OK or \
        status != Variant.Status.NOT_WORKING and not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    if restore:
        combos = data.combos.filter(id__in=variant_def.included_ids)
        variant.identity = merge_identities(variant.uses.values_list('identity', flat=True))
        variant.zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
        variant.cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
        variant.other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
        variant.mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
        variant.description = '\n'.join(c.description for c in combos if len(c.description) > 0)
        variant.status = Variant.Status.NEW if ok else Variant.Status.NOT_WORKING
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    should_save = not ok or restore
    return VariantBulkSaveItem(
        should_save=should_save,
        variant=variant,
        uses=None,
        requires=None,
        of=variant_def.of_ids,
        includes=variant_def.included_ids,
        produces=subtract_removed_features(data, variant_def.included_ids, variant_def.feature_ids) - data.utility_features_ids,
    )


def create_variant(
        data: Data,
        unique_id: str,
        variant_def: VariantDefinition,
        job: Job = None):
    combos = [data.id_to_combo[c_id] for c_id in variant_def.included_ids]
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
        identity=merge_identities([data.id_to_card[c_id].identity for c_id in variant_def.card_ids]),
        generated_by=job)
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    return VariantBulkSaveItem(
        should_save=True,
        variant=variant,
        uses=variant_def.card_ids,
        requires=variant_def.template_ids,
        of=variant_def.of_ids,
        includes=variant_def.included_ids,
        produces=subtract_removed_features(data, variant_def.included_ids, variant_def.feature_ids) - data.utility_features_ids,
    )


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
        log_into_job(job, msg)
    return result


def perform_bulk_saves(to_create: list[VariantBulkSaveItem], to_update: list[VariantBulkSaveItem]):
    batch_size = 999
    Variant.objects.bulk_create((v.variant for v in to_create if v.should_save), batch_size=batch_size)
    update_fields = ['identity', 'zone_locations', 'cards_state', 'mana_needed', 'other_prerequisites', 'description', 'status']
    Variant.objects.bulk_update((v.variant for v in to_update if v.should_save), fields=update_fields, batch_size=batch_size)
    UsesTable = Variant.uses.through
    UsesTable.objects.bulk_create((UsesTable(variant_id=v.variant.id, card_id=c) for v in to_create if v.should_save for c in v.uses), batch_size=batch_size)
    RequiresTable = Variant.requires.through
    RequiresTable.objects.bulk_create((RequiresTable(variant_id=v.variant.id, template_id=t) for v in to_create if v.should_save for t in v.requires), batch_size=batch_size)
    OfTable = Variant.of.through
    OfTable.objects.all().delete()
    OfTable.objects.bulk_create((OfTable(variant_id=v.variant.id, combo_id=c) for v in to_create + to_update for c in v.of), batch_size=batch_size)
    IncludesTable = Variant.includes.through
    IncludesTable.objects.all().delete()
    IncludesTable.objects.bulk_create((IncludesTable(variant_id=v.variant.id, combo_id=c) for v in to_create + to_update for c in v.includes), batch_size=batch_size)
    ProducesTable = Variant.produces.through
    ProducesTable.objects.all().delete()
    ProducesTable.objects.bulk_create((ProducesTable(variant_id=v.variant.id, feature_id=f) for v in to_create + to_update for f in v.produces), batch_size=batch_size)


def generate_variants(job: Job = None) -> tuple[int, int, int]:
    logging.info('Fetching variants set to RESTORE...')
    data = Data()
    to_restore = set(k for k, v in data.uid_to_variant.items() if v.status == Variant.Status.RESTORE)
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.uid_to_variant.keys())
    logging.info('Computing combos graph representation...')
    log_into_job(job, 'Computing combos graph representation...')
    variants = get_variants_from_graph(data, job)
    logging.info(f'Saving {len(variants)} variants...')
    log_into_job(job, f'Saving {len(variants)} variants...')
    with transaction.atomic():
        to_bulk_update = list[VariantBulkSaveItem]()
        to_bulk_create = list[VariantBulkSaveItem]()
        for unique_id, variant_def in variants.items():
            if unique_id in old_id_set:
                status = data.uid_to_variant[unique_id].status
                to_bulk_update.append(
                    update_variant(
                        data=data,
                        unique_id=unique_id,
                        variant_def=variant_def,
                        status=status,
                        restore=unique_id in to_restore))
            else:
                variant_to_save = create_variant(
                    data=data,
                    unique_id=unique_id,
                    variant_def=variant_def,
                    job=job)
                to_bulk_create.append(variant_to_save)
        perform_bulk_saves(to_bulk_create, to_bulk_update)
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
