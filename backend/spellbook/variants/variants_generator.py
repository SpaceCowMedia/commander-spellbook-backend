import gc
import logging
import multiprocessing
import re
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import chain
from typing import Callable, Sequence
from django.utils.functional import cached_property
from django.db import transaction
from multiprocessing_utils import fork_is_available, resolve_workers, split_into_chunks
from .multiset import FrozenMultiset
from .variant_data import Data, CardInVariantRow, TemplateInVariantRow, FeatureProducedByVariantRow
from .variant_set import VariantSet
from .combo_graph import FeatureWithAttributes, Graph, GraphError, cardid, templateid, featureid
from .generation_tracking import (
    GenerationPlan, GenerationScope, plan_full_generation, plan_incremental_generation,
    compute_fingerprints, load_stored_fingerprints, store_fingerprints,
)
from spellbook.models import Combo, FeatureNeededInCombo, Variant, CardInVariant, TemplateInVariant, ZoneLocation, CardType
from spellbook.models import Card, Template, VariantAlias, Ingredient, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo
from spellbook.models import id_from_cards_and_templates_ids, merge_mana_costs, join_with_conjunction, DEFAULT_BATCH_SIZE
from spellbook.models.constants import DEFAULT_CARD_LIMIT, DEFAULT_VARIANT_LIMIT, HIGHER_CARD_LIMIT, LOWER_VARIANT_LIMIT


# ---------------------------------------------------------------------------
# Constants and type aliases
# ---------------------------------------------------------------------------

_VARIANTS_TO_TRIGGER_LOG = 200

LogFunction = Callable[[str], None]
ProgressFunction = Callable[[int, int], None]

# Fields of a Variant row that generation may modify on existing variants
_VARIANT_UPDATE_FIELDS = [
    'status',
    'mana_needed',
    'is_mana_needed_an_accurate_minimum',
    'easy_prerequisites',
    'notable_prerequisites',
    'description',
    'notes',
    'comment',
    'generated_by',
] + Variant.computed_fields()

_INGREDIENT_UPDATE_FIELDS = ('zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity')

# Parallelism is only worth its overhead above these workload sizes;
# it also requires the fork start method, so it is disabled on other platforms.
MIN_COMBOS_FOR_PARALLELISM = 64
MIN_VARIANTS_FOR_PARALLELISM = 2048

FEATURE_REPLACEMENT_PATTERN = re.compile(r'\[\[(?P<key>.+?)(?:\|(?P<alias>[^$|]+?))?(?:\$(?P<selector>[1-9]\d*)(?:\|(?P<postfix_alias>[^$|]+?))?)?\]\]', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class VariantRecipeDefinition:
    card_ids: FrozenMultiset[cardid]
    template_ids: FrozenMultiset[templateid]


@dataclass
class VariantDefinition(VariantRecipeDefinition):
    of_ids: set[int]
    feature_ids: FrozenMultiset[featureid]
    included_ids: set[int]
    feature_replacements: dict[FeatureWithAttributes, list[VariantRecipeDefinition]]
    needed_combos: set[int]
    needed_features_of_cards: set[int]


@dataclass
class VariantBulkSaveItem:
    # Data fields
    variant: Variant
    variant_changed: bool
    # Relationships fields
    uses: list[CardInVariant]
    requires: list[TemplateInVariant]
    produces: list[FeatureProducedByVariant]
    # Rows that have to be inserted or updated in the database
    uses_to_create: list[CardInVariant] = field(default_factory=list)
    uses_to_update: list[CardInVariant] = field(default_factory=list)
    requires_to_create: list[TemplateInVariant] = field(default_factory=list)
    requires_to_update: list[TemplateInVariant] = field(default_factory=list)
    produces_to_create: list[FeatureProducedByVariant] = field(default_factory=list)
    produces_to_update: list[FeatureProducedByVariant] = field(default_factory=list)
    of: set[int] = field(default_factory=set)
    includes: set[int] = field(default_factory=set)

    @cached_property
    def produces_ids(self) -> set[int]:
        return {p.feature_id for p in self.produces}


# ---------------------------------------------------------------------------
# Graph phase: computing the variant definitions from the combo graph
# ---------------------------------------------------------------------------

def _build_definitions_from_variant_set(
    graph: Graph,
    combo: Combo,
    variant_set: VariantSet,
    result: dict[str, VariantDefinition],
) -> None:
    variants = graph.results(variant_set)
    for variant in variants:
        id = id_from_cards_and_templates_ids(variant.cards.distinct_elements(), variant.templates.distinct_elements())
        if id in result:
            result[id].of_ids.add(combo.id)
            continue
        needed_combo_ids = variant.needed_combos.copy()
        # Adding the current combo to the needed combos in case it is not already there
        # Which can happen if the combo does not produce useful features
        needed_combo_ids.add(combo.id)
        feature_replacements = {
            feature: [
                VariantRecipeDefinition(
                    card_ids=ingredients.cards,
                    template_ids=ingredients.templates,
                ) for ingredients in replacements
            ]
            for feature, replacements in variant.replacements.items()
        }
        logging.debug(f'Found new variant for combo {combo.id}: {id}')
        result[id] = VariantDefinition(
            card_ids=variant.cards,
            template_ids=variant.templates,
            feature_ids=variant.features,
            included_ids=variant.combos,
            of_ids={combo.id},
            feature_replacements=feature_replacements,
            needed_combos=needed_combo_ids,
            needed_features_of_cards=variant.needed_feature_of_cards,
        )


def _merge_variant_definitions(target: dict[str, VariantDefinition], source: dict[str, VariantDefinition]) -> None:
    for id, variant_definition in source.items():
        existing = target.get(id)
        if existing is None:
            target[id] = variant_definition
        else:
            existing.of_ids.update(variant_definition.of_ids)


# State inherited by forked worker processes for the graph phase
_GRAPH_WORKER_STATE: Graph | None = None


def _graph_phase_worker(combos: list[Combo]) -> dict[str, VariantDefinition]:
    assert _GRAPH_WORKER_STATE is not None
    graph = _GRAPH_WORKER_STATE
    result = dict[str, VariantDefinition]()
    for combo in combos:
        try:
            variant_set = graph.variants(combo.id)
            _build_definitions_from_variant_set(graph, combo, variant_set, result)
        except GraphError as e:
            raise GraphError(f'Error while computing variants for generator combo {combo} with ID {combo.id}: {e}')
    return result


def get_variants_from_graph(
    data: Data,
    combos: Sequence[Combo] | None = None,
    log: LogFunction = lambda _: None,
    log_error: LogFunction = lambda _: None,
    progress: ProgressFunction = lambda x, t: None,
    workers: int = 1,
) -> dict[str, VariantDefinition]:
    global _GRAPH_WORKER_STATE
    combos_by_status = dict[tuple[bool, bool], list[Combo]]()
    generator_combos = list(combos) if combos is not None else data.generator_combos
    results_progress_multiplier = 10
    progress_total = len(generator_combos) * (1 + results_progress_multiplier)
    progress_current = 0
    for combo in generator_combos:
        allows_many_cards = combo.allow_many_cards
        allows_multiple_copies = combo.allow_multiple_copies
        combos_by_status.setdefault((allows_many_cards, allows_multiple_copies), []).append(combo)
    result = dict[str, VariantDefinition]()
    for (allows_many_cards, allows_multiple_copies), combos_of_group in combos_by_status.items():
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
            card_limit=card_limit,
            variant_limit=variant_limit,
            allow_multiple_copies=allows_multiple_copies,
        )
        if workers > 1 and fork_is_available() and len(combos_of_group) >= MIN_COMBOS_FOR_PARALLELISM:
            log(f'Computing all variants for {len(combos_of_group)} combos with {workers} workers...')
            chunks = split_into_chunks(combos_of_group, workers)
            # The forked workers never touch the inherited database connections,
            # so they can be safely left open in the parent process
            _GRAPH_WORKER_STATE = graph
            try:
                context = multiprocessing.get_context('fork')
                with context.Pool(processes=min(workers, len(chunks))) as pool:
                    for group_result in pool.imap(_graph_phase_worker, chunks):
                        _merge_variant_definitions(result, group_result)
                        progress_current += (1 + results_progress_multiplier) * sum(map(len, chunks)) // len(chunks)
                        progress(min(progress_current, progress_total), progress_total)
            finally:
                _GRAPH_WORKER_STATE = None
            continue
        log('Computing all variants recipes, following combos\' requirements graphs...')
        total = len(combos_of_group)
        index = 0
        variant_sets: list[tuple[Combo, VariantSet]] = []
        for combo in combos_of_group:
            try:
                variant_set = graph.variants(combo.id)
            except GraphError:
                log_error(f'Error while computing all variants for generator combo {combo} with ID {combo.id}')
                raise
            variant_sets.append((combo, variant_set))
            progress_current += 1
            if len(variant_set) > _VARIANTS_TO_TRIGGER_LOG or index % _VARIANTS_TO_TRIGGER_LOG == 0 or index == total - 1:
                log(f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
                progress(progress_current, progress_total)
            index += 1
        log('Processing all recipes to find all the produced results and more...')
        index = 0
        for combo, variant_set in variant_sets:
            if len(variant_set) > _VARIANTS_TO_TRIGGER_LOG:
                log(f'About to process results for combo {combo.id} ({index + 1}/{total}) with {len(variant_set)} variants...')
            try:
                _build_definitions_from_variant_set(graph, combo, variant_set, result)
            except GraphError:
                log_error(f'Error while computing all results for generator combo {combo} with ID {combo.id}')
                raise
            progress_current += results_progress_multiplier
            if len(variant_set) > _VARIANTS_TO_TRIGGER_LOG or index % _VARIANTS_TO_TRIGGER_LOG == 0 or index == total - 1:
                log(f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
                progress(progress_current, progress_total)
            index += 1
    return result


# ---------------------------------------------------------------------------
# Restore phase: building the Django objects from the variant definitions
# ---------------------------------------------------------------------------

def subtract_features(data: Data, includes: set[int], features: FrozenMultiset[featureid]) -> FrozenMultiset[featureid]:
    to_remove = {r.feature_id for c in includes for r in data.combo_to_removed_features[c]}
    return FrozenMultiset({f: c for f, c in features.items() if f not in data.utility_features_ids and f not in to_remove})


def get_default_zone_location_for_card(card: Card) -> ZoneLocation:
    if card.is_of_type(CardType.INSTANT) or card.is_of_type(CardType.SORCERY):
        return ZoneLocation.HAND
    return ZoneLocation.BATTLEFIELD


def update_state_with_default(data: Data, destination: Ingredient) -> None:
    if isinstance(destination, CardInVariant):
        destination.zone_locations = get_default_zone_location_for_card(data.id_to_card[destination.card_id])
    else:
        destination.zone_locations = Ingredient._meta.get_field('zone_locations').get_default()
    destination.battlefield_card_state = ''
    destination.exile_card_state = ''
    destination.graveyard_card_state = ''
    destination.library_card_state = ''
    destination.must_be_commander = False


def update_state(destination: Ingredient, initial_states: Sequence[Ingredient]) -> None:
    zone_locations = initial_states[0].zone_locations
    for initial_state in initial_states[1:]:
        zone_locations = ''.join(
            location
            for location in zone_locations
            if location in initial_state.zone_locations
        ) or zone_locations or initial_state.zone_locations
    destination.zone_locations = zone_locations
    destination.battlefield_card_state = join_with_conjunction(state.battlefield_card_state for state in initial_states)
    destination.exile_card_state = join_with_conjunction(state.exile_card_state for state in initial_states)
    destination.graveyard_card_state = join_with_conjunction(state.graveyard_card_state for state in initial_states)
    destination.library_card_state = join_with_conjunction(state.library_card_state for state in initial_states)
    destination.must_be_commander = any(state.must_be_commander for state in initial_states)


def _copy_state_from_row(destination: CardInVariant | TemplateInVariant, row: CardInVariantRow | TemplateInVariantRow) -> None:
    destination.zone_locations = row.zone_locations
    destination.battlefield_card_state = row.battlefield_card_state
    destination.exile_card_state = row.exile_card_state
    destination.graveyard_card_state = row.graveyard_card_state
    destination.library_card_state = row.library_card_state
    destination.must_be_commander = row.must_be_commander
    destination.order = row.order


def _ingredient_changed(ingredient: CardInVariant | TemplateInVariant, row: CardInVariantRow | TemplateInVariantRow) -> bool:
    for field_name in _INGREDIENT_UPDATE_FIELDS:
        if getattr(ingredient, field_name) != getattr(row, field_name):
            return True
    return False


def apply_replacements(
    data: Data,
    text: str,
    replacements: dict[FeatureWithAttributes, list[tuple[list[Card], list[Template]]]],
    included_combos: set[int],
) -> str:
    replacements_strings = defaultdict[str, list[str]](list)
    features_needed_by_included_combos = [feature_needed for included_combo_id in included_combos for feature_needed in data.combo_to_needed_features[included_combo_id]]
    for feature, replacement_list in replacements.items():
        corresponding_needed_features = [feature_needed for feature_needed in features_needed_by_included_combos if feature_needed.feature_id == feature.feature.id]
        if corresponding_needed_features and not any(data.feature_needed_in_combo_to_attributes_matcher[corresponding_needed_feature.id].matches(feature.attributes) for corresponding_needed_feature in corresponding_needed_features):
            # if all combos needing that feature don't find a match with attributes the replacement is not applied
            continue
        for cards, templates in replacement_list:
            names = [
                c.name.split(',', 2)[0]
                if ',' in c.name and ' // ' not in c.name and c.is_of_type(CardType.LEGENDARY) and c.is_of_type(CardType.CREATURE)
                else c.name
                for c in cards
            ] + [
                t.name
                for t in templates
            ]
            replacement = ' + '.join(names)
            replacements_strings[feature.feature.name].append(replacement)

    def replacement_with_fallback(key: str, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
        selector_index = 0
        if selector:
            try:
                selector_index = int(selector) - 1
            except ValueError:
                return otherwise
        strings = replacements_strings[key]
        try:
            result = strings[selector_index]
        except IndexError:
            return otherwise
        if alias:
            replacements_strings[alias] = strings
        if postfix_alias:
            replacements_strings.setdefault(postfix_alias, []).append(result)
        return result

    return FEATURE_REPLACEMENT_PATTERN.sub(
        lambda m: replacement_with_fallback(m.group('key'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
        text,
    )


def _restore_variant(
        data: Data,
        variant: Variant,
        variant_def: VariantDefinition,
        restore_fields: bool,
) -> VariantBulkSaveItem:
    # Prepare related objects collections
    used_cards: list[CardInVariant] = []
    old_uses_rows: dict[int, CardInVariantRow] = {}
    for card_id, quantity in variant_def.card_ids.items():
        card_in_variant = CardInVariant(card_id=card_id, variant=variant, quantity=quantity)
        old_row = data.variant_uses_card_dict.get((card_id, variant.id))
        if old_row is not None:
            card_in_variant.id = old_row.id
            old_uses_rows[card_id] = old_row
            _copy_state_from_row(card_in_variant, old_row)
        used_cards.append(card_in_variant)
    required_templates: list[TemplateInVariant] = []
    old_requires_rows: dict[int, TemplateInVariantRow] = {}
    for template_id, quantity in variant_def.template_ids.items():
        template_in_variant = TemplateInVariant(template_id=template_id, variant=variant, quantity=quantity)
        old_row = data.variant_requires_template_dict.get((template_id, variant.id))
        if old_row is not None:
            template_in_variant.id = old_row.id
            old_requires_rows[template_id] = old_row
            _copy_state_from_row(template_in_variant, old_row)
        required_templates.append(template_in_variant)
    generator_combos = [data.id_to_combo[c_id] for c_id in sorted(variant_def.of_ids)]
    other_combos = [data.id_to_combo[c_id] for c_id in sorted(variant_def.included_ids - variant_def.of_ids)]
    needed_combos = [*generator_combos, *(c for c in other_combos if c.id in variant_def.needed_combos)]
    needed_feature_of_cards = [data.id_to_feature_of_card[f_id] for f_id in sorted(variant_def.needed_features_of_cards)]
    produces_ids = subtract_features(data, variant_def.included_ids, variant_def.feature_ids)
    produced_features = list[FeatureProducedByVariant]()
    old_produces_rows: dict[int, FeatureProducedByVariantRow] = {}
    for feature_id, quantity in produces_ids.items():
        produced_feature = FeatureProducedByVariant(feature=data.id_to_feature[feature_id], variant=variant, quantity=quantity)
        old_row = data.variant_produces_feature_dict.get((feature_id, variant.id))
        if old_row is not None:
            produced_feature.id = old_row.id
            old_produces_rows[feature_id] = old_row
        produced_features.append(produced_feature)
    produced_features.sort(key=lambda f: f.feature.name)
    uses = dict[int, CardInVariant]()
    for card_in_variant in used_cards:
        if card_in_variant.card_id not in old_uses_rows:
            card_in_variant.order = 0  # will be updated later
        uses[card_in_variant.card_id] = card_in_variant
    requires = dict[int, TemplateInVariant]()
    for template_in_variant in required_templates:
        if template_in_variant.template_id not in old_requires_rows:
            template_in_variant.order = 0  # will be updated later
        requires[template_in_variant.template_id] = template_in_variant
    if restore_fields:
        # update the variant status
        variant.status = Variant.Status.NEW
        # re-generate the text fields
        replacements = {
            feature_wth_attributes: [
                ([data.id_to_card[i] for i in recipe.card_ids.distinct_elements()], [data.id_to_template[i] for i in recipe.template_ids.distinct_elements()])
                for recipe in recipes
            ]
            for feature_wth_attributes, recipes in variant_def.feature_replacements.items()
        }
        mana_needed_list = [c.mana_needed for c in needed_combos if len(c.mana_needed) > 0]
        easy_prerequisites_list = [c.easy_prerequisites for c in needed_combos if c.easy_prerequisites]
        notable_prerequisites_list = [c.notable_prerequisites for c in needed_combos if c.notable_prerequisites]

        card_initial_states = defaultdict[int, list[Ingredient]](list)
        template_initial_states = defaultdict[int, list[Ingredient]](list)
        for feature_of_card in needed_feature_of_cards:
            card_initial_states[feature_of_card.card_id].append(feature_of_card)
            if feature_of_card.mana_needed:
                mana_needed_list.append(feature_of_card.mana_needed)
            if feature_of_card.easy_prerequisites:
                easy_prerequisites_list.append(feature_of_card.easy_prerequisites)
            if feature_of_card.notable_prerequisites:
                notable_prerequisites_list.append(feature_of_card.notable_prerequisites)

        variant.easy_prerequisites = apply_replacements(data, '\n'.join(easy_prerequisites_list), replacements, variant_def.needed_combos)
        variant.notable_prerequisites = apply_replacements(data, '\n'.join(notable_prerequisites_list), replacements, variant_def.needed_combos)
        variant.mana_needed = apply_replacements(data, merge_mana_costs(mana_needed_list), replacements, variant_def.needed_combos)
        variant.is_mana_needed_an_accurate_minimum = not variant.mana_needed or all(
            c.is_mana_needed_an_accurate_minimum
            for c in needed_combos
        )
        variant.description = apply_replacements(data, '\n'.join(c.description for c in needed_combos if len(c.description) > 0), replacements, variant_def.needed_combos)
        variant.notes = apply_replacements(data, '\n'.join(c.notes for c in needed_combos if len(c.notes) > 0), replacements, variant_def.needed_combos)
        variant.comment = apply_replacements(data, '\n'.join(c.comment for c in needed_combos if len(c.comment) > 0), replacements, variant_def.needed_combos)

        card_zone_locations_overrides = defaultdict[int, defaultdict[str, int]](lambda: defaultdict(int))
        template_zone_locations_overrides = defaultdict[int, defaultdict[str, int]](lambda: defaultdict(int))
        card_features_for_override = defaultdict[int, set[FeatureNeededInCombo]](set)
        template_features_for_override = defaultdict[int, set[FeatureNeededInCombo]](set)
        for combo in needed_combos:
            # Computing used cards initial state
            for card_in_combo in data.combo_to_cards[combo.id]:
                if card_in_combo.card_id in uses:
                    card_initial_states[card_in_combo.card_id].append(card_in_combo)
            # Computing required templates initial state
            for template_in_combo in data.combo_to_templates[combo.id]:
                if template_in_combo.template_id in requires:
                    template_initial_states[template_in_combo.template_id].append(template_in_combo)
            # Applying zone locations overrides
            for feature_in_combo in data.combo_to_needed_features[combo.id]:
                if feature_in_combo.zone_locations:
                    for feature_attributes, feature_replacements in variant_def.feature_replacements.items():
                        if feature_attributes.feature.id == feature_in_combo.feature_id \
                                and data.feature_needed_in_combo_to_attributes_matcher[feature_in_combo.id].matches(feature_attributes.attributes):
                            for feature_replacement in feature_replacements:
                                # Apply the override to all cards replacing the feature
                                for card in feature_replacement.card_ids.distinct_elements():
                                    card_features_for_override[card].add(feature_in_combo)
                                    for location in feature_in_combo.zone_locations:
                                        card_zone_locations_overrides[card][location] += 1
                                for template in feature_replacement.template_ids.distinct_elements():
                                    template_features_for_override[template].add(feature_in_combo)
                                    for location in feature_in_combo.zone_locations:
                                        template_zone_locations_overrides[template][location] += 1
        # Merging the initial states collected for each ingredient
        for card_in_variant in used_cards:
            if card_initial_states[card_in_variant.card_id]:
                update_state(card_in_variant, card_initial_states[card_in_variant.card_id])
            else:
                update_state_with_default(data, card_in_variant)
        for template_in_variant in required_templates:
            if template_initial_states[template_in_variant.template_id]:
                update_state(template_in_variant, template_initial_states[template_in_variant.template_id])
            else:
                update_state_with_default(data, template_in_variant)
        for used_card in used_cards:
            override_score = max(card_zone_locations_overrides[used_card.card_id].values(), default=0)
            if override_score > 0:
                used_card.zone_locations = ''.join(
                    location
                    for location, count in card_zone_locations_overrides[used_card.card_id].items()
                    if count == override_score
                )
            used_card.battlefield_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.battlefield_card_state
                    for f in card_features_for_override[used_card.card_id]
                    if ZoneLocation.BATTLEFIELD in f.zone_locations and f.battlefield_card_state
                ) or used_card.battlefield_card_state if ZoneLocation.BATTLEFIELD in used_card.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            used_card.exile_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.exile_card_state
                    for f in card_features_for_override[used_card.card_id]
                    if ZoneLocation.EXILE in f.zone_locations and f.exile_card_state
                ) or used_card.exile_card_state if ZoneLocation.EXILE in used_card.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            used_card.graveyard_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.graveyard_card_state
                    for f in card_features_for_override[used_card.card_id]
                    if ZoneLocation.GRAVEYARD in f.zone_locations and f.graveyard_card_state
                ) or used_card.graveyard_card_state if ZoneLocation.GRAVEYARD in used_card.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            used_card.library_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.library_card_state
                    for f in card_features_for_override[used_card.card_id]
                    if ZoneLocation.LIBRARY in f.zone_locations and f.library_card_state
                ) or used_card.library_card_state if ZoneLocation.LIBRARY in used_card.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
        for required_template in required_templates:
            override_score = max(template_zone_locations_overrides[required_template.template_id].values(), default=0)
            if override_score > 0:
                required_template.zone_locations = ''.join(
                    location
                    for location, count in template_zone_locations_overrides[required_template.template_id].items()
                    if count == override_score
                )
            required_template.battlefield_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.battlefield_card_state
                    for f in template_features_for_override[required_template.template_id]
                    if ZoneLocation.BATTLEFIELD in f.zone_locations and f.battlefield_card_state
                ) or required_template.battlefield_card_state if ZoneLocation.BATTLEFIELD in required_template.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            required_template.exile_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.exile_card_state
                    for f in template_features_for_override[required_template.template_id]
                    if ZoneLocation.EXILE in f.zone_locations and f.exile_card_state
                ) or required_template.exile_card_state if ZoneLocation.EXILE in required_template.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            required_template.graveyard_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.graveyard_card_state
                    for f in template_features_for_override[required_template.template_id]
                    if ZoneLocation.GRAVEYARD in f.zone_locations and f.graveyard_card_state
                ) or required_template.graveyard_card_state if ZoneLocation.GRAVEYARD in required_template.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )
            required_template.library_card_state = apply_replacements(
                data,
                '\n'.join(
                    f.library_card_state
                    for f in template_features_for_override[required_template.template_id]
                    if ZoneLocation.LIBRARY in f.zone_locations and f.library_card_state
                ) or required_template.library_card_state if ZoneLocation.LIBRARY in required_template.zone_locations else '',
                replacements,
                variant_def.needed_combos,
            )

    # Ordering ingredients by ascending replaceability and ascending order in combos
    cards_ordering: dict[int, tuple[int, int, int, int]] = {c: (0, 0, 0, 0) for c in uses}
    templates_ordering: dict[int, tuple[int, int, int, int]] = {t: (0, 0, 0, 0) for t in requires}
    for combos, is_generator in ((generator_combos, True), (other_combos, False)):
        for combo in combos:
            for i, card_in_combo in enumerate(reversed(data.combo_to_cards[combo.id]), start=1):
                if card_in_combo.card_id in cards_ordering:
                    t = cards_ordering[card_in_combo.card_id]
                    cards_ordering[card_in_combo.card_id] = (t[0] + 1, t[1] + i, t[2], t[3]) if is_generator else (t[0], t[1], t[2] + 1, t[3] + i)
            for i, template_in_combo in enumerate(reversed(data.combo_to_templates[combo.id]), start=1):
                if template_in_combo.template_id in templates_ordering:
                    t = templates_ordering[template_in_combo.template_id]
                    templates_ordering[template_in_combo.template_id] = (t[0] + 1, t[1] + i, t[2], t[3]) if is_generator else (t[0], t[1], t[2] + 1, t[3] + i)

    def uses_list():
        for i, v in enumerate(sorted(cards_ordering, key=lambda k: cards_ordering[k], reverse=True), start=1):
            civ = uses[v]
            civ.order = i
            yield civ

    def requires_list():
        for i, v in enumerate(sorted(templates_ordering, key=lambda k: templates_ordering[k], reverse=True), start=1):
            tiv = requires[v]
            tiv.order = i
            yield tiv

    # Recomputing some variant fields
    variant.update_variant_from_recipe(Variant.Recipe(
        [(c, data.id_to_card[c.card_id]) for c in used_cards],
        [(t, data.id_to_template[t.template_id]) for t in required_templates],
        [(f, data.id_to_feature[f.feature_id]) for f in produced_features],
    ))

    save_item = VariantBulkSaveItem(
        variant=variant,
        variant_changed=True,
        uses=list(uses_list()),
        requires=list(requires_list()),
        of=variant_def.of_ids,
        includes=variant_def.included_ids,
        produces=produced_features,
    )
    # Compute which relationship rows are new and which existing ones have changed
    for card_in_variant in save_item.uses:
        old_row = old_uses_rows.get(card_in_variant.card_id)
        if old_row is None:
            save_item.uses_to_create.append(card_in_variant)
        elif _ingredient_changed(card_in_variant, old_row):
            save_item.uses_to_update.append(card_in_variant)
    for template_in_variant in save_item.requires:
        old_row = old_requires_rows.get(template_in_variant.template_id)
        if old_row is None:
            save_item.requires_to_create.append(template_in_variant)
        elif _ingredient_changed(template_in_variant, old_row):
            save_item.requires_to_update.append(template_in_variant)
    for feature_produced in save_item.produces:
        old_row = old_produces_rows.get(feature_produced.feature_id)
        if old_row is None:
            save_item.produces_to_create.append(feature_produced)
        elif feature_produced.quantity != old_row.quantity:
            save_item.produces_to_update.append(feature_produced)
    return save_item


def _update_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        variant: Variant,
        restore: bool,
        job: str | None) -> VariantBulkSaveItem:
    old_values = [getattr(variant, field_name) for field_name in _VARIANT_UPDATE_FIELDS]
    save_item = _restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=restore,
    )
    if restore:
        variant.generated_by = job
    # perform pre_save early, outside of the save transaction, to also include
    # its effects in the change detection
    variant.pre_save()
    save_item.variant_changed = any(
        getattr(variant, field_name) != old_value
        for field_name, old_value in zip(_VARIANT_UPDATE_FIELDS, old_values)
    )
    return save_item


def _create_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        job: str | None) -> VariantBulkSaveItem:
    variant = Variant(
        id=id,
        generated_by=job,
    )
    save_item = _restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=True,
    )
    variant.pre_save()
    return save_item


# State inherited by forked worker processes for the restore phase
_RESTORE_WORKER_STATE: tuple[Data, dict[str, VariantDefinition], dict[str, Variant], set[str], str | None] | None = None


def _restore_phase_worker(ids: list[str]) -> tuple[list[VariantBulkSaveItem], list[VariantBulkSaveItem]]:
    assert _RESTORE_WORKER_STATE is not None
    data, variants, variant_instances, to_restore, job = _RESTORE_WORKER_STATE
    return _restore_variants_chunk(data, variants, variant_instances, to_restore, job, ids)


def _restore_variants_chunk(
    data: Data,
    variants: dict[str, VariantDefinition],
    variant_instances: dict[str, Variant],
    to_restore: set[str],
    job: str | None,
    ids: list[str],
) -> tuple[list[VariantBulkSaveItem], list[VariantBulkSaveItem]]:
    to_bulk_update = list[VariantBulkSaveItem]()
    to_bulk_create = list[VariantBulkSaveItem]()
    for id in ids:
        variant_def = variants[id]
        variant = variant_instances.get(id)
        if variant is not None:
            to_bulk_update.append(_update_variant(
                data=data,
                id=id,
                variant_def=variant_def,
                variant=variant,
                restore=id in to_restore,
                job=job,
            ))
        else:
            to_bulk_create.append(_create_variant(
                data=data,
                id=id,
                variant_def=variant_def,
                job=job,
            ))
    return to_bulk_update, to_bulk_create


def restore_variants(
    data: Data,
    variants: dict[str, VariantDefinition],
    variant_instances: dict[str, Variant],
    to_restore: set[str],
    job: str | None,
    workers: int = 1,
) -> tuple[list[VariantBulkSaveItem], list[VariantBulkSaveItem]]:
    global _RESTORE_WORKER_STATE
    ids = list(variants.keys())
    if workers > 1 and fork_is_available() and len(ids) >= MIN_VARIANTS_FOR_PARALLELISM:
        chunks = split_into_chunks(ids, workers)
        # The forked workers never touch the inherited database connections,
        # so they can be safely left open in the parent process
        _RESTORE_WORKER_STATE = (data, variants, variant_instances, to_restore, job)
        try:
            context = multiprocessing.get_context('fork')
            with context.Pool(processes=min(workers, len(chunks))) as pool:
                to_bulk_update = list[VariantBulkSaveItem]()
                to_bulk_create = list[VariantBulkSaveItem]()
                for chunk_updates, chunk_creates in pool.imap(_restore_phase_worker, chunks):
                    to_bulk_update.extend(chunk_updates)
                    to_bulk_create.extend(chunk_creates)
                return to_bulk_update, to_bulk_create
        finally:
            _RESTORE_WORKER_STATE = None
    return _restore_variants_chunk(data, variants, variant_instances, to_restore, job, ids)


# ---------------------------------------------------------------------------
# Save phase: writing the changes to the database
# ---------------------------------------------------------------------------

def _perform_bulk_saves(
    data: Data,
    to_create: list[VariantBulkSaveItem],
    to_update: list[VariantBulkSaveItem],
    log: LogFunction = lambda _: None,
    progress: ProgressFunction = lambda x, t: None,
) -> None:
    step_count = 7
    log('Prepare variants...')
    variant_bulk_create = tuple(v.variant for v in to_create)
    variant_bulk_update = tuple(v.variant for v in to_update if v.variant_changed)
    variant_bulk_update_fields = _VARIANT_UPDATE_FIELDS
    progress(1, step_count)
    log('Prepare variant related entities...')
    cardinvariant_bulk_create = tuple(c for v in chain(to_create, to_update) for c in v.uses_to_create)
    cardinvariant_bulk_update = tuple(c for v in to_update for c in v.uses_to_update)
    cardinvariant_bulk_update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
    progress(2, step_count)
    templateinvariant_bulk_create = tuple(t for v in chain(to_create, to_update) for t in v.requires_to_create)
    templateinvariant_bulk_update = tuple(t for v in to_update for t in v.requires_to_update)
    templateinvariant_bulk_update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
    progress(3, step_count)
    of_bulk_delete = tuple(
        of.id
        for v in to_update
        for of in data.variant_to_of_sets[v.variant.id]
        if of.combo_id not in v.of
    )
    of_bulk_create = tuple(
        VariantOfCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_create
        for c in v.of
    ) + tuple(
        VariantOfCombo(variant_id=v.variant.id, combo_id=combo_id)
        for v in to_update
        for combo_id in v.of
        if (combo_id, v.variant.id) not in data.variant_of_combo_dict
    )
    progress(4, step_count)
    includes_bulk_delete = tuple(
        includes.id
        for v in to_update
        for includes in data.variant_to_includes_sets[v.variant.id]
        if includes.combo_id not in v.includes
    )
    includes_bulk_create = tuple(
        VariantIncludesCombo(variant_id=v.variant.id, combo_id=c)
        for v in to_create
        for c in v.includes
    ) + tuple(
        VariantIncludesCombo(variant_id=v.variant.id, combo_id=combo_id)
        for v in to_update
        for combo_id in v.includes
        if (combo_id, v.variant.id) not in data.variant_includes_combo_dict
    )
    progress(5, step_count)
    produces_bulk_delete = tuple(
        produces.id
        for v in to_update
        for produces in data.variant_to_produces[v.variant.id]
        if produces.feature_id not in v.produces_ids
    )
    produces_bulk_create = tuple(
        i
        for v in chain(to_create, to_update)
        for i in v.produces_to_create
    )
    produces_bulk_update = tuple(
        p
        for v in to_update
        for p in v.produces_to_update
    )
    produces_bulk_update_fields = ['quantity']
    progress(6, step_count)
    log('Perform bulk updates...')
    with transaction.atomic():
        # delete
        if of_bulk_delete:
            VariantOfCombo.objects.filter(id__in=of_bulk_delete).delete()
        if includes_bulk_delete:
            VariantIncludesCombo.objects.filter(id__in=includes_bulk_delete).delete()
        if produces_bulk_delete:
            FeatureProducedByVariant.objects.filter(id__in=produces_bulk_delete).delete()
        # update
        Variant.objects.bulk_update(variant_bulk_update, fields=variant_bulk_update_fields, batch_size=DEFAULT_BATCH_SIZE, skip_pre_save=True)
        CardInVariant.objects.bulk_update(cardinvariant_bulk_update, fields=cardinvariant_bulk_update_fields, batch_size=DEFAULT_BATCH_SIZE)
        TemplateInVariant.objects.bulk_update(templateinvariant_bulk_update, fields=templateinvariant_bulk_update_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureProducedByVariant.objects.bulk_update(produces_bulk_update, fields=produces_bulk_update_fields, batch_size=DEFAULT_BATCH_SIZE)
        # create
        Variant.objects.bulk_create(variant_bulk_create, batch_size=DEFAULT_BATCH_SIZE, skip_pre_save=True)
        CardInVariant.objects.bulk_create(cardinvariant_bulk_create, batch_size=DEFAULT_BATCH_SIZE)
        TemplateInVariant.objects.bulk_create(templateinvariant_bulk_create, batch_size=DEFAULT_BATCH_SIZE)
        FeatureProducedByVariant.objects.bulk_create(produces_bulk_create, batch_size=DEFAULT_BATCH_SIZE)
        VariantOfCombo.objects.bulk_create(of_bulk_create, batch_size=DEFAULT_BATCH_SIZE)
        VariantIncludesCombo.objects.bulk_create(includes_bulk_create, batch_size=DEFAULT_BATCH_SIZE)


def sync_variant_aliases(data: Data, added_variants_ids: set[str], deleted_variants_ids: set[str]) -> tuple[int, int]:
    deleted_count, _ = VariantAlias.objects.filter(id__in=added_variants_ids).delete()
    deleted_variants = [data.id_to_variant[id] for id in sorted(deleted_variants_ids)]
    variant_aliases = [
        VariantAlias(
            id=v.id,
            description=f'Added because "{v.name}" has been removed from the database.'
        )
        for v in deleted_variants
        if v.status in Variant.public_statuses()
    ]
    added_count = len(VariantAlias.objects.bulk_create(variant_aliases, ignore_conflicts=True, batch_size=DEFAULT_BATCH_SIZE))
    return added_count, deleted_count


# ---------------------------------------------------------------------------
# Entry point: orchestrating the whole generation
# ---------------------------------------------------------------------------

def generate_variants(
    combo: int | None = None,
    job: str | None = None,
    log: LogFunction = lambda _: None,
    log_error: LogFunction = lambda _: None,
    progress: ProgressFunction = lambda x, t: None,
    incremental: bool = False,
    workers: int | None = None,
) -> tuple[int, int, int]:
    workers = resolve_workers(workers)
    progress(0, 100)
    if combo is not None:
        log(f'Variant generation started for combo {combo}.')
    else:
        log('Variant generation started for all combos.')
    log('Fetching data...')
    data = Data()
    progress(8, 100)
    # The loaded dataset is read-only reference data from here on: freezing it
    # exempts it from garbage collector scans for the rest of the generation
    gc.collect()
    gc.freeze()
    try:
        return _generate_variants(data, combo, job, log, log_error, progress, incremental, workers)
    finally:
        gc.unfreeze()


def _generate_variants(
    data: Data,
    combo: int | None,
    job: str | None,
    log: LogFunction,
    log_error: LogFunction,
    progress: ProgressFunction,
    incremental: bool,
    workers: int,
) -> tuple[int, int, int]:
    log('Computing entity fingerprints...')
    current_fingerprints = compute_fingerprints(data)
    if combo is not None:
        plan = GenerationPlan(
            scope=GenerationScope.SINGLE,
            combos_to_generate=[data.id_to_combo[combo]],
            regenerated_combo_ids={combo},
        )
    elif incremental:
        plan = plan_incremental_generation(data, current_fingerprints, load_stored_fingerprints())
        if plan.fallback_reason is not None:
            log(f'Falling back to full generation: {plan.fallback_reason}')
        else:
            log(f'Incremental generation: {len(plan.combos_to_generate)} of {len(data.generator_combos)} generator combos have to be regenerated.')
    else:
        plan = plan_full_generation(data)
    progress(10, 100)
    to_restore = set(k for k, v in data.id_to_variant.items() if v.status == Variant.Status.RESTORE or len(data.variant_to_of_sets[k]) == 0)
    log('Fetching all variant unique ids...')
    old_id_set = set(data.id_to_variant.keys())
    progress(12, 100)
    log('Computing combos graph representation...')
    variants = get_variants_from_graph(
        data,
        plan.combos_to_generate,
        log,
        log_error,
        progress=lambda x, t: progress(12 + int(x / t * 70), 100),
        workers=workers,
    )
    if plan.scope is not GenerationScope.FULL:
        # Preserve the relationships with generator combos outside of the regeneration scope
        for id, variant_def in variants.items():
            of_rows = data.variant_to_of_sets.get(id)
            if of_rows:
                variant_def.of_ids.update(of_row.combo_id for of_row in of_rows if of_row.combo_id not in plan.regenerated_combo_ids)
    log(f'Processing {len(variants)} variants...')
    variant_instances = data.fetch_variants(id for id in variants if id in old_id_set)
    to_bulk_update, to_bulk_create = restore_variants(
        data=data,
        variants=variants,
        variant_instances=variant_instances,
        to_restore=to_restore,
        job=job,
        workers=workers,
    )
    progress(85, 100)
    log(f'Saving {len(variants)} variants...')
    _perform_bulk_saves(data, to_bulk_create, to_bulk_update, log, progress=lambda x, t: progress(85 + int(x / t * 10), 100))
    progress(95, 100)
    log(f'Saved {len(variants)} variants.')
    new_id_set = set(variants.keys())
    added = new_id_set - old_id_set
    restored = new_id_set & to_restore
    log(f'Added {len(added)} new variants.')
    log(f'Updated {len(restored)} variants.')
    if plan.scope is GenerationScope.FULL:
        to_delete = old_id_set - new_id_set
    elif plan.scope is GenerationScope.INCREMENTAL:
        # An existing variant is deleted only when all of its generator combos
        # were regenerated and none of them produces it anymore
        to_delete = {
            id
            for id in old_id_set - new_id_set
            if data.variant_to_of_sets[id] and all(
                of_row.combo_id in plan.regenerated_combo_ids
                for of_row in data.variant_to_of_sets[id]
            )
        }
    else:
        to_delete = set[str]()
    delete_query = Variant.objects.filter(id__in=to_delete)
    _, deleted_counts = delete_query.delete()
    progress(97, 100)
    deleted_count = deleted_counts.get('spellbook.Variant', 0)
    log(f'Deleted {deleted_count} variants.')
    added_aliases, deleted_aliases = sync_variant_aliases(data, added, to_delete)
    log(f'Added {added_aliases} new aliases, deleted {deleted_aliases} aliases.')
    if plan.scope is not GenerationScope.SINGLE:
        # Only a full or incremental generation leaves the database in a state
        # that is consistent with the computed fingerprints
        store_fingerprints(current_fingerprints)
    progress(100, 100)
    log('Done.')
    return len(added), len(restored), deleted_count
