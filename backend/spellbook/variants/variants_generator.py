from itertools import chain
import logging
import re
from collections import defaultdict
from .multiset import FrozenMultiset
from dataclasses import dataclass
from django.utils.functional import cached_property
from django.db import transaction
from .variant_data import Data
from .combo_graph import FeatureWithAttributes, Graph, VariantSet, cardid, templateid, featureid
from spellbook.models import Combo, FeatureNeededInCombo, Job, Variant, CardInVariant, TemplateInVariant, ZoneLocation, CardType
from spellbook.models import Card, Template, VariantAlias, Ingredient, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo
from spellbook.models import id_from_cards_and_templates_ids, merge_mana_costs, DEFAULT_BATCH_SIZE
from spellbook.utils import log_into_job
from spellbook.models.constants import DEFAULT_CARD_LIMIT, DEFAULT_VARIANT_LIMIT, HIGHER_CARD_LIMIT, LOWER_VARIANT_LIMIT


VARIANTS_TO_TRIGGER_LOG = 200


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


def get_variants_from_graph(data: Data, single_combo: int | None, job: Job | None, log_count: int) -> dict[str, VariantDefinition]:
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
        log_into_job(job, 'Processing combos that allow ' + ' and '.join(conditions) + '...')
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
        log_into_job(job, 'Computing all variants recipes, following combos\' requirements graphs...')
        total = len(combos)
        index = 0
        variant_sets: list[tuple[Combo, VariantSet]] = []
        for combo in combos:
            try:
                variant_set = graph.variants(combo.id)
            except Graph.GraphError:
                log_into_job(job, f'Error while computing all variants for generator combo {combo} with ID {combo.id}')
                raise
            variant_sets.append((combo, variant_set))
            if len(variant_set) > VARIANTS_TO_TRIGGER_LOG or index % log_count == 0 or index == total - 1:
                log_into_job(job, f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
            index += 1
        log_into_job(job, 'Processing all recipes to find all the produced results and more...')
        index = 0
        for combo, variant_set in variant_sets:
            if len(variant_set) > VARIANTS_TO_TRIGGER_LOG:
                log_into_job(job, f'About to process results for combo {combo.id} ({index + 1}/{total}) with {len(variant_set)} variants...')
            try:
                variants = graph.results(variant_set)
            except Graph.GraphError:
                log_into_job(job, f'Error while computing all results for generator combo {combo} with ID {combo.id}')
                raise
            for variant in variants:
                id = id_from_cards_and_templates_ids(variant.cards.distinct_elements(), variant.templates.distinct_elements())
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
                if id in result:
                    x = result[id]
                    x.of_ids.add(combo.id)
                else:
                    logging.debug(f'Found new variant for combo {combo.id} ({index + 1}/{total}): {id}')
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
                    if single_combo is not None:
                        # avoid removing all previous generator combos when generating for a single combo
                        result[id].of_ids.update(of.combo_id for of in data.variant_to_of_sets.get(id, []))
            if len(variant_set) > VARIANTS_TO_TRIGGER_LOG or index % log_count == 0 or index == total - 1:
                log_into_job(job, f'{index + 1}/{total} combos processed (just processed combo {combo.id})')
            index += 1
    return result


def subtract_features(data: Data, includes: set[int], features: FrozenMultiset[featureid]) -> FrozenMultiset[featureid]:
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

    @cached_property
    def produces_ids(self) -> set[int]:
        return {p.feature_id for p in self.produces}


def get_default_zone_location_for_card(card: Card) -> ZoneLocation:
    if card.is_of_type(CardType.INSTANT) or card.is_of_type(CardType.SORCERY):
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
        ) or dst.zone_locations or src.zone_locations
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


FEATURE_REPLACEMENT_REGEX = r'\[\[(?P<key>.+?)(?:\|(?P<alias>[^$|]+?))?(?:\$(?P<selector>[1-9]\d*)(?:\|(?P<postfix_alias>[^$|]+?))?)?\]\]'


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

    return re.sub(
        FEATURE_REPLACEMENT_REGEX,
        lambda m: replacement_with_fallback(m.group('key'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
        text,
        flags=re.IGNORECASE,
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
        if (c_id, variant.id) in data.variant_uses_card_dict:
            civ = data.variant_uses_card_dict[(c_id, variant.id)]
            civ.quantity = quantity
        else:
            civ = CardInVariant(card=data.id_to_card[c_id], variant=variant, quantity=quantity)
        used_cards.append(civ)
    required_templates: list[TemplateInVariant] = []
    for t_id, quantity in variant_def.template_ids.items():
        if (t_id, variant.id) in data.variant_requires_template_dict:
            tiv = data.variant_requires_template_dict[(t_id, variant.id)]
            tiv.quantity = quantity
        else:
            tiv = TemplateInVariant(template=data.id_to_template[t_id], variant=variant, quantity=quantity)
        required_templates.append(tiv)
    generator_combos = [data.id_to_combo[c_id] for c_id in sorted(variant_def.of_ids)]
    other_combos = [data.id_to_combo[c_id] for c_id in sorted(variant_def.included_ids - variant_def.of_ids)]
    needed_combos = [*generator_combos, *(c for c in other_combos if c.id in variant_def.needed_combos)]
    needed_feature_of_cards = [data.id_to_feature_of_card[f_id] for f_id in sorted(variant_def.needed_features_of_cards)]
    produces_ids = subtract_features(data, variant_def.included_ids, variant_def.feature_ids)
    produced_features = list[FeatureProducedByVariant]()
    for f_id, quantity in produces_ids.items():
        if (f_id, variant.id) in data.variant_produces_feature_dict:
            fiv = data.variant_produces_feature_dict[(f_id, variant.id)]
            fiv.feature = data.id_to_feature[f_id]
            fiv.quantity = quantity
        else:
            fiv = FeatureProducedByVariant(feature=data.id_to_feature[f_id], variant=variant, quantity=quantity)
        produced_features.append(fiv)
    produced_features.sort(key=lambda f: f.feature.name)
    uses = dict[int, CardInVariant]()
    for card_in_variant in used_cards:
        card_in_variant.order = 0  # will be updated later
        uses[card_in_variant.card_id] = card_in_variant
    requires = dict[int, TemplateInVariant]()
    for template_in_variant in required_templates:
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

        for card_in_variant in used_cards:
            update_state_with_default(data, card_in_variant)
        for template_in_variant in required_templates:
            update_state_with_default(data, template_in_variant)
        uses_updated = set[int]()
        requires_updated = set[int]()
        for feature_of_card in needed_feature_of_cards:
            to_edit = uses[feature_of_card.card_id]
            if to_edit.card_id not in uses_updated:
                update_state(to_edit, feature_of_card, overwrite=True)
                uses_updated.add(to_edit.card_id)
            else:
                update_state(to_edit, feature_of_card)
            if feature_of_card.mana_needed:
                mana_needed_list.append(feature_of_card.mana_needed)
            if feature_of_card.easy_prerequisites:
                easy_prerequisites_list.append(feature_of_card.easy_prerequisites)
            if feature_of_card.notable_prerequisites:
                notable_prerequisites_list.append(feature_of_card.notable_prerequisites)

        variant.easy_prerequisites = apply_replacements(data, '\n'.join(easy_prerequisites_list), replacements, variant_def.needed_combos)
        variant.notable_prerequisites = apply_replacements(data, '\n'.join(notable_prerequisites_list), replacements, variant_def.needed_combos)
        variant.mana_needed = apply_replacements(data, merge_mana_costs(mana_needed_list), replacements, variant_def.needed_combos)
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
                    to_edit = uses[card_in_combo.card_id]
                    if to_edit.card_id not in uses_updated:
                        update_state(to_edit, card_in_combo, overwrite=True)
                        uses_updated.add(to_edit.card_id)
                    else:
                        update_state(to_edit, card_in_combo)
            # Computing required templates initial state
            for template_in_combo in data.combo_to_templates[combo.id]:
                if template_in_combo.template_id in requires:
                    to_edit = requires[template_in_combo.template_id]
                    if to_edit.template_id not in requires_updated:
                        update_state(to_edit, template_in_combo, overwrite=True)
                        requires_updated.add(to_edit.template_id)
                    else:
                        update_state(to_edit, template_in_combo)
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
    old_results_count = variant.result_count
    old_name = variant.name
    save_item = restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=restore,
    )
    if restore:
        variant.generated_by = job
    save_item.should_update = restore or status != variant.status or old_results_count != variant.result_count or variant.name != old_name
    return save_item


def create_variant(
        data: Data,
        id: str,
        variant_def: VariantDefinition,
        job: Job | None):
    variant = Variant(
        id=id,
        generated_by=job,
    )
    save_item = restore_variant(
        data=data,
        variant=variant,
        variant_def=variant_def,
        restore_fields=True,
    )
    save_item.should_update = True
    return save_item


def perform_bulk_saves(data: Data, to_create: list[VariantBulkSaveItem], to_update: list[VariantBulkSaveItem], job: Job | None = None):
    variant_bulk_create = tuple(v.variant for v in to_create)
    variant_bulk_update = tuple(v.variant for v in to_update)
    # perform pre_save outside the transaction to reduce lock time
    log_into_job(job, 'Preprocess variants...')
    for variant in chain(variant_bulk_create, variant_bulk_update):
        variant.pre_save()
    variant_bulk_update_fields = ['status', 'mana_needed', 'easy_prerequisites', 'notable_prerequisites', 'description', 'notes', 'comment', 'generated_by'] + Variant.computed_fields()
    cardinvariant_bulk_create = tuple(c for v in to_create for c in v.uses)
    cardinvariant_bulk_update = tuple(c for v in to_update for c in v.uses)
    cardinvariant_bulk_update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
    templateinvariant_bulk_create = tuple(t for v in to_create for t in v.requires)
    templateinvariant_bulk_update = tuple(t for v in to_update for t in v.requires)
    templateinvariant_bulk_update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order', 'quantity']
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
    produces_bulk_delete = tuple(
        produces.id
        for v in to_update
        for produces in data.variant_to_produces[v.variant.id]
        if produces.feature_id not in v.produces_ids
    )
    produces_bulk_create = tuple(
        i
        for v in to_create
        for i in v.produces
    ) + tuple(
        i
        for v in to_update
        for i in v.produces
        if (i.feature_id, v.variant.id) not in data.variant_produces_feature_dict
    )
    produces_bulk_update = tuple(
        p
        for v in to_update
        for p in v.produces
        if (p.feature_id, v.variant.id) in data.variant_produces_feature_dict
    )
    produces_bulk_update_fields = ['quantity']
    log_into_job(job, 'Perform bulk updates...')
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


def generate_variants(combo: int | None = None, job: Job | None = None, log_count: int = VARIANTS_TO_TRIGGER_LOG) -> tuple[int, int, int]:
    if combo is not None:
        log_into_job(job, f'Variant generation started for combo {combo}.')
    else:
        log_into_job(job, 'Variant generation started for all combos.')
    log_into_job(job, 'Fetching data...')
    data = Data()
    to_restore = set(k for k, v in data.id_to_variant.items() if v.status == Variant.Status.RESTORE or len(data.variant_to_of_sets[k]) == 0)
    log_into_job(job, 'Fetching all variant unique ids...')
    old_id_set = set(data.id_to_variant.keys())
    log_into_job(job, 'Computing combos graph representation...')
    variants = get_variants_from_graph(data, combo, job, log_count)
    log_into_job(job, f'Processing {len(variants)} variants...')
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
            if variant_to_update.should_update:
                to_bulk_update.append(variant_to_update)
        else:
            status = Variant.Status.NEW
            variant_to_save = create_variant(
                data=data,
                id=id,
                variant_def=variant_def,
                job=job)
            to_bulk_create.append(variant_to_save)
    log_into_job(job, f'Saving {len(variants)} variants...')
    perform_bulk_saves(data, to_bulk_create, to_bulk_update)
    log_into_job(job, f'Saved {len(variants)} variants.')
    new_id_set = set(variants.keys())
    added = new_id_set - old_id_set
    restored = new_id_set & to_restore
    log_into_job(job, f'Added {len(added)} new variants.')
    log_into_job(job, f'Updated {len(restored)} variants.')
    if combo is None:
        to_delete = old_id_set - new_id_set
    else:
        to_delete = set[str]()
    delete_query = Variant.objects.filter(id__in=to_delete)
    _, deleted_counts = delete_query.delete()
    deleted_count = deleted_counts.get('spellbook.Variant', 0)
    log_into_job(job, f'Deleted {deleted_count} variants...')
    added_aliases, deleted_aliases = sync_variant_aliases(data, added, to_delete)
    log_into_job(job, f'Added {added_aliases} new aliases, deleted {deleted_aliases} aliases.')
    log_into_job(job, 'Done.')
    return len(added), len(restored), deleted_count
