import logging
import re
from collections import defaultdict
from multiset import FrozenMultiset, Multiset, BaseMultiset
from itertools import chain
from dataclasses import dataclass
from django.db import transaction
from .utils import includes_any
from .variant_data import Data, debug_queries
from .combo_graph import Graph, VariantSet
from spellbook.models import Combo, Job, Variant, CardInVariant, TemplateInVariant, id_from_cards_and_templates_ids, Playable, Card, Template, VariantAlias, Ingredient, Feature, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo, ZoneLocation
from spellbook.utils import log_into_job


DEFAULT_CARD_LIMIT = 5
DEFAULT_VARIANT_LIMIT = 10000
HIGHER_CARD_LIMIT = 100
LOWER_VARIANT_LIMIT = 100


@dataclass
class VariantRecipeDefinition:
    card_ids: FrozenMultiset
    template_ids: FrozenMultiset


@dataclass
class VariantDefinition(VariantRecipeDefinition):
    of_ids: set[int]
    feature_ids: Multiset
    included_ids: set[int]
    feature_replacements: defaultdict[int, list[VariantRecipeDefinition]]
    needed_features: set[int]
    needed_combos: set[int]


def get_variants_from_graph(data: Data, single_combo: int | None, job: Job | None, log_count: int) -> dict[str, VariantDefinition]:
    def log(msg: str):
        logging.info(msg)
        log_into_job(job, msg)
    combos_by_status = dict[tuple[bool, bool], list[Combo]]()
    generator_combos = (data.id_to_combo[single_combo],) if single_combo is not None else data.generator_combos
    for combo in generator_combos:
        allows_many_cards = combo.allow_many_cards
        allows_multiple_copies = combo.allow_multiple_copies
        combos_by_status.setdefault((allows_many_cards, allows_multiple_copies), []).append(combo)
    result = dict[str, VariantDefinition]()
    for (allows_many_cards, allows_multiple_copies), combos in combos_by_status.items():
        conditions = ([f'at most {HIGHER_CARD_LIMIT} cards'] if allows_many_cards else [f'at most {DEFAULT_CARD_LIMIT} cards']) + \
            (['multiple copies'] if allows_multiple_copies else ['only singleton copies'])
        log('Processing combos that allow ' + ' and '.join(conditions) + '...')
        card_limit = DEFAULT_CARD_LIMIT
        variant_limit = DEFAULT_VARIANT_LIMIT
        if allows_many_cards:
            card_limit = HIGHER_CARD_LIMIT
            variant_limit = LOWER_VARIANT_LIMIT
        graph = Graph(
            data,
            log=log,
            card_limit=card_limit,
            variant_limit=variant_limit,
            allow_multiple_copies=allows_multiple_copies,
        )
        log('Computing all variants recipes, following combos\' requirements graphs...')
        total = len(combos)
        index = 0
        variant_sets: list[tuple[Combo, VariantSet]] = []
        for combo in combos:
            variant_set = graph.variants(combo.id)
            variant_sets.append((combo, variant_set))
            if len(variant_set) > 50 or index % log_count == 0 or index == total - 1:
                log(f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
            index += 1
        log('Processing all recipes to find all the produced results and more...')
        index = 0
        for combo, variant_set in variant_sets:
            if len(variant_set) > 50:
                log(f'About to process results for combo {combo.id} ({index + 1}/{total}) with {len(variant_set)} variants...')
            for variant in graph.results(variant_set):
                cards_ids = variant.cards
                templates_ids = variant.templates
                id = id_from_cards_and_templates_ids(cards_ids.distinct_elements(), templates_ids.distinct_elements())
                feature_ids = variant.features
                needed_feature_ids = variant.needed_features
                needed_combo_ids = variant.needed_combos
                combo_ids = variant.combos
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
                else:
                    logging.debug(f'Found new variant for combo {combo.id} ({index + 1}/{total}): {id}')
                    result[id] = VariantDefinition(
                        card_ids=cards_ids,
                        template_ids=templates_ids,
                        feature_ids=Multiset(feature_ids),
                        included_ids=combo_ids,
                        of_ids={combo.id},
                        feature_replacements=defaultdict(list, feature_replacements),
                        needed_features=needed_feature_ids,
                        needed_combos=needed_combo_ids,
                    )
            if len(variant_set) > 50 or index % log_count == 0 or index == total - 1:
                log(f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
            index += 1
    return result


def subtract_features(data: Data, includes: set[int], features: BaseMultiset) -> FrozenMultiset:
    to_remove = {r.feature_id for c in includes for r in data.combo_to_removed_features[c]}
    return FrozenMultiset({f: c for f, c in features.items() if f not in data.utility_features_ids and f not in to_remove})


@dataclass
class VariantBulkSaveItem:
    should_update: bool
    # Data fields
    variant: Variant
    # Relationships fields
    uses: list[CardInVariant]
    requires: list[TemplateInVariant]
    produces: list[FeatureProducedByVariant]
    of: set[int]
    includes: set[int]

    def produces_ids(self) -> set[int]:
        if not hasattr(self, '_produces_ids'):
            self._produces_ids = {p.feature_id for p in self.produces}
        return self._produces_ids


def get_default_zone_location_for_card(card: Card) -> str:
    if card.is_instant() or card.is_sorcery():
        return ZoneLocation.HAND
    return ZoneLocation.BATTLEFIELD


def update_state_with_default(data: Data, dst: Ingredient):
    if isinstance(dst, CardInVariant):
        dst.zone_locations = get_default_zone_location_for_card(data.id_to_card[dst.card_id])
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
        dst.zone_locations = ''.join(
            location
            for location in dst.zone_locations
            if location in src.zone_locations
        ) or src.zone_locations
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
            names = [
                c.name.split(',', 2)[0]
                if ',' in c.name and '//' not in c.name and c.is_legendary() and c.is_creature()
                else c.name
                for c in cards
            ] + [
                t.name
                for t in templates
            ]
            replacement = ' + '.join(names)
            replacements_strings[feature.name] = replacement

    def replacement_strategy(key: str, otherwise: str) -> str:
        key = key.strip()
        parts = key.split('|', 2)
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
    # Prepare related objects collections
    used_cards: list[CardInVariant] = []
    for c_id, quantity in variant_def.card_ids.items():
        if (c_id, variant.id) in data.card_variant_dict:
            civ = data.card_variant_dict[(c_id, variant.id)]
            civ.quantity = quantity
        else:
            civ = CardInVariant(card=data.id_to_card[c_id], variant=variant, quantity=quantity)
        used_cards.append(civ)
    required_templates: list[TemplateInVariant] = []
    for t_id, quantity in variant_def.template_ids.items():
        if (t_id, variant.id) in data.template_variant_dict:
            tiv = data.template_variant_dict[(t_id, variant.id)]
            tiv.quantity = quantity
        else:
            tiv = TemplateInVariant(template=data.id_to_template[t_id], variant=variant, quantity=quantity)
        required_templates.append(tiv)
    generator_combos = [data.id_to_combo[c_id] for c_id in variant_def.of_ids]
    included_combos = [data.id_to_combo[c_id] for c_id in variant_def.included_ids]
    produces_ids = subtract_features(data, variant_def.included_ids, variant_def.feature_ids)
    produced_features = [
        FeatureProducedByVariant(
            feature=data.id_to_feature[f_id],
            variant=variant,
            quantity=quantity,
        ) for f_id, quantity in produces_ids.items()
    ]
    produced_features.sort(key=lambda f: f.feature_id)
    # Update variant computed information
    requires_commander = any(c.must_be_commander for c in used_cards) or any(t.must_be_commander for t in required_templates)
    variant.update([data.id_to_card[c.card_id] for c in used_cards], requires_commander)
    uses = dict[int, CardInVariant]()
    for card_in_variant in used_cards:
        card_in_variant.order = 0
        uses[card_in_variant.card_id] = card_in_variant
    requires = dict[int, TemplateInVariant]()
    for template_in_variant in required_templates:
        template_in_variant.order = 0
        requires[template_in_variant.template_id] = template_in_variant
    if restore_fields:
        # prepare data for the update
        needed_features = variant_def.needed_features
        combos_included_for_a_reason = [
            c
            for c in included_combos
            if c.id in variant_def.needed_combos
        ]
        # update the variant status
        variant.status = Variant.Status.NEW
        # re-generate the text fields
        replacements = {
            data.id_to_feature[feature_id]: [
                ([data.id_to_card[i] for i in recipe.card_ids], [data.id_to_template[i] for i in recipe.template_ids])
                for recipe in recipes
            ]
            for feature_id, recipes in variant_def.feature_replacements.items()
        }
        variant.other_prerequisites = apply_replacements('\n'.join(c.other_prerequisites for c in combos_included_for_a_reason if len(c.other_prerequisites) > 0), replacements)
        variant.mana_needed = apply_replacements(' '.join(c.mana_needed for c in combos_included_for_a_reason if len(c.mana_needed) > 0), replacements)
        variant.description = apply_replacements('\n'.join(c.description for c in combos_included_for_a_reason if len(c.description) > 0), replacements)
        variant.notes = apply_replacements('\n'.join(c.notes for c in combos_included_for_a_reason if len(c.notes) > 0), replacements)
        for card_in_variant in used_cards:
            update_state_with_default(data, card_in_variant)
        for template_in_variant in required_templates:
            update_state_with_default(data, template_in_variant)
        uses_updated = set[int]()
        requires_updated = set[int]()
        additional_other_prerequisites: list[str] = []
        for to_edit in used_cards:
            for feature_of_card in data.card_to_features[to_edit.card_id]:
                if not data.id_to_feature[feature_of_card.feature_id].utility or feature_of_card.feature_id in needed_features:
                    if to_edit.card_id not in uses_updated:
                        update_state(to_edit, feature_of_card, overwrite=True)
                        uses_updated.add(to_edit.card_id)
                    else:
                        update_state(to_edit, feature_of_card)
                    additional_other_prerequisites.append(feature_of_card.other_prerequisites)
        if additional_other_prerequisites:
            variant.other_prerequisites = apply_replacements('\n'.join(additional_other_prerequisites), replacements) + '\n' + variant.other_prerequisites
        card_zone_locations_overrides = defaultdict[int, defaultdict[str, int]](lambda: defaultdict(int))
        template_zone_locations_overrides = defaultdict[int, defaultdict[str, int]](lambda: defaultdict(int))
        for combo in combos_included_for_a_reason:
            for card_in_combo in data.combo_to_cards[combo.id]:
                if card_in_combo.card_id in uses:
                    to_edit = uses[card_in_combo.card_id]
                    if to_edit.card_id not in uses_updated:
                        update_state(to_edit, card_in_combo, overwrite=True)
                        uses_updated.add(to_edit.card_id)
                    else:
                        update_state(to_edit, card_in_combo)
            for template_in_combo in data.combo_to_templates[combo.id]:
                if template_in_combo.template_id in requires:
                    to_edit = requires[template_in_combo.template_id]
                    if to_edit.template_id not in requires_updated:
                        update_state(to_edit, template_in_combo, overwrite=True)
                        requires_updated.add(to_edit.template_id)
                    else:
                        update_state(to_edit, template_in_combo)
            for feature_in_combo in data.combo_to_needed_features[combo.id]:
                if feature_in_combo.zone_locations_override:
                    for replacement in variant_def.feature_replacements[feature_in_combo.feature_id]:
                        for card in replacement.card_ids:
                            for location in feature_in_combo.zone_locations_override:
                                card_zone_locations_overrides[card][location] += 1
                        for template in replacement.template_ids:
                            for location in feature_in_combo.zone_locations_override:
                                template_zone_locations_overrides[template][location] += 1
        for used_card in used_cards:
            used_card.battlefield_card_state = apply_replacements(used_card.battlefield_card_state, replacements)
            used_card.exile_card_state = apply_replacements(used_card.exile_card_state, replacements)
            used_card.graveyard_card_state = apply_replacements(used_card.graveyard_card_state, replacements)
            used_card.library_card_state = apply_replacements(used_card.library_card_state, replacements)
            override_score = max(card_zone_locations_overrides[used_card.card_id].values(), default=0)
            if override_score > 0:
                used_card.zone_locations = ''.join(
                    location
                    for location, count in card_zone_locations_overrides[used_card.card_id].items()
                    if count == override_score
                )
        for required_template in required_templates:
            required_template.battlefield_card_state = apply_replacements(required_template.battlefield_card_state, replacements)
            required_template.exile_card_state = apply_replacements(required_template.exile_card_state, replacements)
            required_template.graveyard_card_state = apply_replacements(required_template.graveyard_card_state, replacements)
            required_template.library_card_state = apply_replacements(required_template.library_card_state, replacements)
            override_score = max(template_zone_locations_overrides[required_template.template_id].values(), default=0)
            if override_score > 0:
                required_template.zone_locations = ''.join(
                    location
                    for location, count in template_zone_locations_overrides[required_template.template_id].items()
                    if count == override_score
                )

    # Ordering ingredients by descending replaceability and ascending order in combos
    cards_ordering: dict[int, tuple[int, int]] = {c: (0, 0) for c in uses}
    templates_ordering: dict[int, tuple[int, int]] = {t: (0, 0) for t in requires}
    for i, combo in enumerate(chain(included_combos, generator_combos)):
        for j, card_in_combo in enumerate(reversed(data.combo_to_cards[combo.id])):
            if card_in_combo.card_id in cards_ordering:
                t = cards_ordering[card_in_combo.card_id]
                cards_ordering[card_in_combo.card_id] = (t[0] + i, t[1] + j)
        for j, template_in_combo in enumerate(reversed(data.combo_to_templates[combo.id])):
            if template_in_combo.template_id in templates_ordering:
                t = templates_ordering[template_in_combo.template_id]
                templates_ordering[template_in_combo.template_id] = (t[0] + i, t[1] + j)

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
        cards={data.id_to_card[civ.card_id].name: civ.quantity for civ in uses_list()},
        templates={data.id_to_template[tiv.template_id].name: tiv.quantity for tiv in requires_list()},
        features_needed={},
        features_produced={
            f: q
            for f, q in sorted(
                [
                    (data.id_to_feature[f.feature_id].name, f.quantity)
                    for f in produced_features
                ],
            )
        },
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
        produces=produced_features,
    )


def update_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        status: Variant.Status | str,
        restore: bool,
        job: Job | None):
    variant = data.id_to_variant[id]
    ok = status in Variant.public_statuses() or \
        status != Variant.Status.NOT_WORKING and not includes_any(v=variant_def.card_ids, others=(c for c, _ in data.not_working_variants))
    old_results_count = variant.results_count
    old_name = variant.name
    save_item = restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=restore,
    )
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    if restore:
        variant.generated_by = job
    save_item.should_update = restore or status != variant.status or old_results_count != variant.results_count or variant.name != old_name
    return save_item


def create_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        job: Job | None):
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
    ok = not includes_any(v=variant_def.card_ids, others=(c for c, _ in data.not_working_variants))
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    save_item.should_update = True
    return save_item


def perform_bulk_saves(data: Data, to_create: list[VariantBulkSaveItem], to_update: list[VariantBulkSaveItem]):
    Variant.objects.bulk_create([v.variant for v in to_create])
    update_fields = ['name', 'status', 'mana_needed', 'other_prerequisites', 'description', 'notes', 'results_count', 'generated_by'] + Playable.playable_fields()
    Variant.objects.bulk_update([v.variant for v in to_update if v.should_update], fields=update_fields)
    CardInVariant.objects.bulk_create([c for v in to_create for c in v.uses])
    update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
    CardInVariant.objects.bulk_update([c for v in to_update if v.should_update for c in v.uses], fields=update_fields)
    TemplateInVariant.objects.bulk_create([t for v in to_create for t in v.requires])
    update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
    TemplateInVariant.objects.bulk_update([t for v in to_update if v.should_update for t in v.requires], fields=update_fields)
    to_delete_of = [
        i.pk
        for v in to_update
        for c, i in data.variant_to_of[v.variant.id].items()
        if c not in v.of
    ]
    if to_delete_of:
        VariantOfCombo.objects.filter(pk__in=to_delete_of).delete()
    del to_delete_of
    to_create_of = [
        VariantOfCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_create
        for c in v.of
    ] + [
        VariantOfCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_update
        for c in v.of
        if c not in data.variant_to_of[v.variant.id]
    ]
    VariantOfCombo.objects.bulk_create(to_create_of)
    del to_create_of
    to_delete_includes = [
        i.pk
        for v in to_update
        for c, i in data.variant_to_includes[v.variant.id].items()
        if c not in v.includes
    ]
    if to_delete_includes:
        VariantIncludesCombo.objects.filter(pk__in=to_delete_includes).delete()
    del to_delete_includes
    to_create_includes = [
        VariantIncludesCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_create
        for c in v.includes
    ] + [
        VariantIncludesCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_update
        for c in v.includes
        if c not in data.variant_to_includes[v.variant.id]
    ]
    VariantIncludesCombo.objects.bulk_create(to_create_includes)
    del to_create_includes
    to_delete_produces = [
        i.pk
        for v in to_update
        for f, i in data.variant_to_produces[v.variant.id].items()
        if f not in v.produces_ids()
    ]
    if to_delete_produces:
        FeatureProducedByVariant.objects.filter(pk__in=to_delete_produces).delete()
    del to_delete_produces
    to_create_produces = [
        i
        for v in to_create
        for i in v.produces
    ] + [
        i
        for v in to_update
        for i in v.produces
        if i.feature_id not in data.variant_to_produces[v.variant.id]
    ]
    FeatureProducedByVariant.objects.bulk_create(to_create_produces)
    del to_create_produces
    to_update_produces: list[FeatureProducedByVariant] = []
    for v in to_update:
        for i in v.produces:
            old_instance = data.variant_to_produces[v.variant.id].get(i.feature_id)
            if old_instance is not None and \
                    old_instance.quantity != i.quantity:
                i.pk = old_instance.pk
                to_update_produces.append(i)
    update_fields = ['quantity']
    FeatureProducedByVariant.objects.bulk_update(to_update_produces, fields=update_fields)


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


def generate_variants(combo: int | None = None, job: Job | None = None, log_count: int = 100) -> tuple[int, int, int]:
    if combo is not None:
        log_into_job(job, f'Variant generation started for combo {combo}.')
    else:
        log_into_job(job, 'Variant generation started for all combos.')
    logging.info('Fetching data...')
    log_into_job(job, 'Fetching data...')
    data = Data()
    to_restore = set(k for k, v in data.id_to_variant.items() if v.status == Variant.Status.RESTORE or len(data.variant_to_of[k]) == 0)
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.id_to_variant.keys())
    logging.info('Computing combos graph representation...')
    log_into_job(job, 'Computing combos graph representation...')
    debug_queries()
    variants = get_variants_from_graph(data, combo, job, log_count)
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
                restore=id in to_restore,
                job=job)
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
        perform_bulk_saves(data, to_bulk_create, to_bulk_update)
        new_id_set = set(variants.keys())
        added = new_id_set - old_id_set
        restored = new_id_set & to_restore
        logging.info(f'Added {len(added)} new variants.')
        logging.info(f'Updated {len(restored)} variants.')
        if combo is None:
            to_delete = old_id_set - new_id_set
        else:
            to_delete = set()
        delete_query = Variant.objects.filter(id__in=to_delete)
        deleted_count = len(to_delete)
        delete_query.delete()
        logging.info(f'Deleted {deleted_count} variants...')
        added_aliases, deleted_aliases = sync_variant_aliases(data, added, to_delete)
        logging.info(f'Added {added_aliases} new aliases, deleted {deleted_aliases} aliases.')
        logging.info('Done.')
        debug_queries(True)
        return len(added), len(restored), deleted_count
