import logging
import re
from itertools import chain
from dataclasses import dataclass
from django.db import transaction
from .list_utils import includes_any
from .variant_data import Data, debug_queries
from .combo_graph import Graph
from spellbook.models import Combo, Job, Variant, CardInVariant, TemplateInVariant, id_from_cards_and_templates_ids, Playable, Card, Template, VariantAlias, Ingredient, Feature
from spellbook.utils import log_into_job


DEFAULT_CARD_LIMIT = 5
DEFAULT_VARIANT_LIMIT = 10000
HIGHER_CARD_LIMIT = 100
LOWER_VARIANT_LIMIT = 100


@dataclass
class VariantRecipeDefinition:
    card_ids: list[int]
    template_ids: list[int]


@dataclass
class VariantDefinition(VariantRecipeDefinition):
    of_ids: set[int]
    feature_ids: set[int]
    included_ids: set[int]
    feature_replacements: dict[int, list[VariantRecipeDefinition]]


def get_variants_from_graph(data: Data, job: Job | None = None) -> dict[str, VariantDefinition]:
    def log(msg: str):
        logging.info(msg)
        log_into_job(job, msg)
    log('Computing all possible variants:')
    combos_by_status = dict[str, list[Combo]]()
    for combo in data.generator_combos:
        combos_by_status.setdefault(combo.status, []).append(combo)
    result = dict[str, VariantDefinition]()
    total = len(data.generator_combos)
    for status, combos in combos_by_status.items():
        card_limit = DEFAULT_CARD_LIMIT
        variant_limit = DEFAULT_VARIANT_LIMIT
        if status == Combo.Status.GENERATOR_WITH_MANY_CARDS:
            card_limit = HIGHER_CARD_LIMIT
            variant_limit = LOWER_VARIANT_LIMIT
        graph = Graph(data, log=log, card_limit=card_limit, variant_limit=variant_limit)
        for i, combo in enumerate(combos):
            count = 0
            variants = graph.variants(combo.id)
            for variant in variants:
                cards_ids = variant.cards
                templates_ids = variant.templates
                id = id_from_cards_and_templates_ids(cards_ids, templates_ids)
                feature_ids = set(variant.features)
                combo_ids = set(variant.combos)
                feature_replacements = {
                    feature: [
                        VariantRecipeDefinition(
                            card_ids=ingredients.cards,
                            template_ids=ingredients.templates,
                        ) for ingredients in replacements
                    ]
                    for feature, replacements in variant.replacements.items()
                }
                if id in result:
                    x = result[id]
                    x.of_ids.add(combo.id)
                    x.included_ids.update(combo_ids)
                    x.feature_ids.update(feature_ids)
                    for feature, replacements in feature_replacements.items():
                        x.feature_replacements.setdefault(feature, []).extend(replacements)
                else:
                    logging.debug(f'Found new variant for combo {combo.id} ({i + 1}/{total}): {id}')
                    result[id] = VariantDefinition(
                        card_ids=cards_ids,
                        template_ids=templates_ids,
                        feature_ids=feature_ids,
                        included_ids=combo_ids,
                        of_ids={combo.id},
                        feature_replacements=feature_replacements,
                    )
                count += 1
            msg = f'{i + 1}/{total} combos processed (just processed combo {combo.id})'
            if count > 1 or i % 100 == 0 or i == total - 1:
                log(msg)
    return result


def subtract_removed_features(data: Data, includes: set[int], features: set[int]) -> set[int]:
    return features - set(r for c in includes for r in data.combo_to_removed_features[c])


@dataclass
class VariantBulkSaveItem:
    should_update: bool
    # Data fields
    variant: Variant
    # Relationships fields
    uses: list[CardInVariant]
    requires: list[TemplateInVariant]
    of: set[int]
    includes: set[int]
    produces: set[int]


def get_default_zone_location_for_card(card: Card) -> str:
    if any(card_type in card.type_line for card_type in ('Instant', 'Sorcery')):
        return Ingredient.ZoneLocation.HAND
    return Ingredient.ZoneLocation.BATTLEFIELD


def update_state_with_default(dst: Ingredient):
    if isinstance(dst, CardInVariant):
        dst.zone_locations = get_default_zone_location_for_card(dst.card)
    else:
        dst.zone_locations = Ingredient._meta.get_field('zone_locations').get_default()
    dst.battlefield_card_state = ''
    dst.exile_card_state = ''
    dst.graveyard_card_state = ''
    dst.library_card_state = ''
    dst.must_be_commander = False


def update_state(dst: Ingredient, src: Ingredient, overwrite=False):
    if overwrite:
        dst.zone_locations = src.zone_locations
        dst.battlefield_card_state = src.battlefield_card_state
        dst.exile_card_state = src.exile_card_state
        dst.graveyard_card_state = src.graveyard_card_state
        dst.library_card_state = src.library_card_state
        dst.must_be_commander = src.must_be_commander
    else:
        dst.zone_locations = ''.join(location for location in dst.zone_locations if location in src.zone_locations) or src.zone_locations
        if len(dst.battlefield_card_state) > 0:
            dst.battlefield_card_state += ' '
        dst.battlefield_card_state += src.battlefield_card_state
        if len(dst.exile_card_state) > 0:
            dst.exile_card_state += ' '
        dst.exile_card_state += src.exile_card_state
        if len(dst.graveyard_card_state) > 0:
            dst.graveyard_card_state += ' '
        dst.graveyard_card_state += src.graveyard_card_state
        if len(dst.library_card_state) > 0:
            dst.library_card_state += ' '
        dst.library_card_state += src.library_card_state
        dst.must_be_commander = dst.must_be_commander or src.must_be_commander


def apply_replacements(
    text: str,
    replacements: dict[Feature, list[tuple[list[Card], list[Template]]]],
) -> str:
    replacements_strings = dict[str, str]()
    for feature, replacement_list in replacements.items():
        if replacement_list:
            cards, templates = replacement_list[0]
            names = [c.name for c in cards] + [t.name for t in templates]
            replacement = ' + '.join(names)
            replacements_strings[feature.name] = replacement

    def replacement_strategy(key: str, otherwise: str) -> str:
        key = key.strip()
        parts = key.split(':', 2)
        key = parts[0]
        if key in replacements_strings:
            if len(parts) == 2:
                replacements_strings[parts[1]] = replacements_strings[key]
            return replacements_strings[key]
        return otherwise
    return re.sub(
        r'\[\[(?P<key>.+?)\]\]',
        lambda m: replacement_strategy(m.group('key'), m.group(0)),
        text,
    )


def restore_variant(
        data: Data,
        variant: Variant,
        variant_def: VariantDefinition,
        restore_fields: bool,
) -> VariantBulkSaveItem:
    # Set status
    variant.status = Variant.Status.NEW

    # Prepare related objects collections
    used_cards = [
        data.card_in_variant[(c_id, variant.id)]
        if (c_id, variant.id) in data.card_in_variant
        else CardInVariant(card=data.id_to_card[c_id], variant=variant)
        for c_id in variant_def.card_ids
    ]
    required_templates = [
        data.template_in_variant[(t_id, variant.id)]
        if (t_id, variant.id) in data.template_in_variant
        else TemplateInVariant(template=data.id_to_template[t_id], variant=variant)
        for t_id in variant_def.template_ids
    ]
    generator_combos = [data.id_to_combo[c_id] for c_id in variant_def.of_ids]
    included_combos = [data.id_to_combo[c_id] for c_id in variant_def.included_ids]
    produces_ids = subtract_removed_features(data, variant_def.included_ids, variant_def.feature_ids) - data.utility_features_ids
    produced_features = sorted([data.id_to_feature[f_id] for f_id in produces_ids], key=lambda f: f.name)
    # Update variant computed information
    requires_commander = any(c.must_be_commander for c in used_cards) or any(t.must_be_commander for t in required_templates)
    variant.update([c.card for c in used_cards], requires_commander)
    uses = dict[int, CardInVariant]()
    for card_in_variant in used_cards:
        card_in_variant.order = 0
        uses[card_in_variant.card.id] = card_in_variant
    requires = dict[int, TemplateInVariant]()
    for template_in_variant in required_templates:
        template_in_variant.order = 0
        requires[template_in_variant.template.id] = template_in_variant
    if restore_fields:
        # re-generate the text fields
        replacements = {
            data.id_to_feature[feature_id]: [
                ([data.id_to_card[i] for i in recipe.card_ids], [data.id_to_template[i] for i in recipe.template_ids])
                for recipe in recipes
            ]
            for feature_id, recipes in variant_def.feature_replacements.items()
        }
        variant.other_prerequisites = apply_replacements('\n'.join(c.other_prerequisites for c in included_combos if len(c.other_prerequisites) > 0), replacements)
        variant.mana_needed = apply_replacements(' '.join(c.mana_needed for c in included_combos if len(c.mana_needed) > 0), replacements)
        variant.description = apply_replacements('\n'.join(c.description for c in included_combos if len(c.description) > 0), replacements)
        for card_in_variant in used_cards:
            update_state_with_default(card_in_variant)
        for template_in_variant in required_templates:
            update_state_with_default(template_in_variant)
        uses_updated = set[int]()
        requires_updated = set[int]()
        for to_edit in used_cards:
            for feature_of_card in data.card_to_features[to_edit.card.id]:
                if to_edit.card.id not in uses_updated:
                    update_state(to_edit, feature_of_card, overwrite=True)
                    uses_updated.add(to_edit.card.id)
                else:
                    update_state(to_edit, feature_of_card)
        for combo in included_combos:
            for card_in_combo in data.combo_to_cards[combo.id]:
                if card_in_combo.card.id in uses:
                    to_edit = uses[card_in_combo.card.id]
                    if to_edit.card.id not in uses_updated:
                        update_state(to_edit, card_in_combo, overwrite=True)
                        uses_updated.add(to_edit.card.id)
                    else:
                        update_state(to_edit, card_in_combo)
            for template_in_combo in data.combo_to_templates[combo.id]:
                if template_in_combo.template.id in requires:
                    to_edit = requires[template_in_combo.template.id]
                    if to_edit.template.id not in requires_updated:
                        update_state(to_edit, template_in_combo, overwrite=True)
                        requires_updated.add(to_edit.template.id)
                    else:
                        update_state(to_edit, template_in_combo)
        for used_card in used_cards:
            used_card.battlefield_card_state = apply_replacements(used_card.battlefield_card_state, replacements)
            used_card.exile_card_state = apply_replacements(used_card.exile_card_state, replacements)
            used_card.graveyard_card_state = apply_replacements(used_card.graveyard_card_state, replacements)
            used_card.library_card_state = apply_replacements(used_card.library_card_state, replacements)

    # Ordering ingredients by descending replaceability and ascending order in combos
    cards_ordering: dict[int, tuple[int, int]] = {c: (0, 0) for c in uses}
    templates_ordering: dict[int, tuple[int, int]] = {t: (0, 0) for t in requires}
    for i, combo in enumerate(chain(included_combos, generator_combos)):
        for j, card_in_combo in enumerate(reversed(data.combo_to_cards[combo.id])):
            if card_in_combo.card.id in cards_ordering:
                t = cards_ordering[card_in_combo.card.id]
                cards_ordering[card_in_combo.card.id] = (t[0] + i, t[1] + j)
        for j, template_in_combo in enumerate(reversed(data.combo_to_templates[combo.id])):
            if template_in_combo.template.id in templates_ordering:
                t = templates_ordering[template_in_combo.template.id]
                templates_ordering[template_in_combo.template.id] = (t[0] + i, t[1] + j)

    def uses_list():
        for i, v in enumerate(sorted(cards_ordering, key=lambda k: cards_ordering[k], reverse=True)):
            civ = uses[v]
            civ.order = i
            yield civ

    def requires_list():
        for i, v in enumerate(sorted(templates_ordering, key=lambda k: templates_ordering[k], reverse=True)):
            tiv = requires[v]
            tiv.order = i
            yield tiv

    # Recomputing some variant fields
    variant.name = Variant.compute_name(
        cards=[data.id_to_card[civ.card_id] for civ in uses_list()],  # type: ignore
        templates=[data.id_to_template[tiv.template_id] for tiv in requires_list()],  # type: ignore
        features_needed=[],
        features_produced=produced_features,
    )
    variant.results_count = len(produces_ids)

    # Return the final object
    return VariantBulkSaveItem(
        should_update=False,
        variant=variant,
        uses=list(uses_list()),
        requires=list(requires_list()),
        of=variant_def.of_ids,
        includes=variant_def.included_ids,
        produces=produces_ids,
    )


def update_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        status: Variant.Status | str,
        restore=False):
    variant = data.id_to_variant[id]
    ok = status in Variant.public_statuses() or \
        status != Variant.Status.NOT_WORKING and not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    old_results_count = variant.results_count
    save_item = restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=restore,
    )
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    save_item.should_update = restore or status != variant.status or old_results_count != variant.results_count
    return save_item


def create_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        job: Job | None = None):
    variant = Variant(
        id=id,
        generated_by=job,
        cards_count=len(variant_def.card_ids) + len(variant_def.template_ids),
    )
    save_item = restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=True,
    )
    ok = not includes_any(v=frozenset(variant_def.card_ids), others=data.not_working_variants)
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    save_item.should_update = True
    return save_item


def perform_bulk_saves(to_create: list[VariantBulkSaveItem], to_update: list[VariantBulkSaveItem]):
    Variant.objects.bulk_create([v.variant for v in to_create])
    if to_update:
        update_fields = ['name', 'status', 'mana_needed', 'other_prerequisites', 'description', 'results_count'] + Playable.playable_fields()
        Variant.objects.bulk_update([v.variant for v in to_update if v.should_update], fields=update_fields)
    CardInVariant.objects.bulk_create([c for v in to_create for c in v.uses])
    if to_update:
        update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order']
        CardInVariant.objects.bulk_update([c for v in to_update if v.should_update for c in v.uses], fields=update_fields)
    TemplateInVariant.objects.bulk_create([t for v in to_create for t in v.requires])
    if to_update:
        update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order']
        TemplateInVariant.objects.bulk_update([t for v in to_update if v.should_update for t in v.requires], fields=update_fields)
    OfTable = Variant.of.through
    if to_update:
        OfTable.objects.all().delete()
    OfTable.objects.bulk_create([
        OfTable(
            variant_id=v.variant.id,
            combo_id=c) for v in chain(to_create, to_update) for c in v.of])
    IncludesTable = Variant.includes.through
    if to_update:
        IncludesTable.objects.all().delete()
    IncludesTable.objects.bulk_create([
        IncludesTable(
            variant_id=v.variant.id,
            combo_id=c) for v in chain(to_create, to_update) for c in v.includes])
    ProducesTable = Variant.produces.through
    if to_update:
        ProducesTable.objects.all().delete()
    ProducesTable.objects.bulk_create([
        ProducesTable(
            variant_id=v.variant.id,
            feature_id=f) for v in chain(to_create, to_update) for f in v.produces])


def sync_variant_aliases(data: Data, added_variants_ids: set[str], deleted_variants_ids: set[str]) -> tuple[int, int]:
    deleted_count, _ = VariantAlias.objects.filter(id__in=added_variants_ids).delete()
    deleted_variants = [data.id_to_variant[id] for id in sorted(deleted_variants_ids)]
    variant_aliases = [
        VariantAlias(
            id=v.id,
            description=f'Added because {v.name} has been removed from the database.'
        )
        for v in deleted_variants
        if v.status in Variant.public_statuses()
    ]
    added_count = len(VariantAlias.objects.bulk_create(variant_aliases, ignore_conflicts=True))
    return added_count, deleted_count


def generate_variants(job: Job | None = None) -> tuple[int, int, int]:
    logging.info('Fetching data...')
    log_into_job(job, 'Fetching data...')
    data = Data()
    to_restore = set(k for k, v in data.id_to_variant.items() if v.status == Variant.Status.RESTORE)
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.id_to_variant.keys())
    logging.info('Computing combos graph representation...')
    log_into_job(job, 'Computing combos graph representation...')
    debug_queries()
    variants = get_variants_from_graph(data, job)
    logging.info(f'Saving {len(variants)} variants...')
    log_into_job(job, f'Saving {len(variants)} variants...')
    debug_queries()
    to_bulk_update = list[VariantBulkSaveItem]()
    to_bulk_create = list[VariantBulkSaveItem]()
    for id, variant_def in variants.items():
        if id in old_id_set:
            status = data.id_to_variant[id].status
            variant_to_update = update_variant(
                data=data,
                id=id,
                variant_def=variant_def,
                status=status,
                restore=id in to_restore)
            to_bulk_update.append(variant_to_update)
        else:
            variant_to_save = create_variant(
                data=data,
                id=id,
                variant_def=variant_def,
                job=job)
            to_bulk_create.append(variant_to_save)
        debug_queries()
    with transaction.atomic():
        perform_bulk_saves(to_bulk_create, to_bulk_update)
        new_id_set = set(variants.keys())
        to_delete = old_id_set - new_id_set
        added = new_id_set - old_id_set
        restored = new_id_set & to_restore
        logging.info(f'Added {len(added)} new variants.')
        logging.info(f'Updated {len(restored)} variants.')
        delete_query = data.variants.filter(id__in=to_delete)
        deleted_count = delete_query.count()
        delete_query.delete()
        logging.info(f'Deleted {deleted_count} variants...')
        added_aliases, deleted_aliases = sync_variant_aliases(data, added, to_delete)
        logging.info(f'Added {added_aliases} new aliases, deleted {deleted_aliases} aliases.')
        logging.info('Done.')
        debug_queries(True)
        return len(added), len(restored), deleted_count
