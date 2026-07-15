import hashlib
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Iterable
from django.utils import timezone
from spellbook.models import Combo, Variant, Playable, VariantGenerationFingerprints
from spellbook.models.constants import DEFAULT_CARD_LIMIT, DEFAULT_VARIANT_LIMIT, HIGHER_CARD_LIMIT, LOWER_VARIANT_LIMIT
from .variant_data import Data


# Fingerprints of all the entities of a given kind, keyed by kind and then by entity id
Fingerprints = dict[str, dict[int, str]]

# Bump this version to force a full regeneration
# whenever the generation algorithm changes in a way that affects its output.
_FINGERPRINT_VERSION = 1

_META_KIND = 'meta'
_ENTITY_KINDS = ('card', 'template', 'feature', 'combo')

_CARD_FINGERPRINT_FIELDS = (
    'name',
    'type_line',
    'keywords',
    'reserved',
    'game_changer',
    'tutor',
    'mass_land_denial',
    'extra_turn',
)

_COMBO_FINGERPRINT_FIELDS = (
    'status',
    'allow_many_cards',
    'allow_multiple_copies',
    'mana_needed',
    'is_mana_needed_an_accurate_minimum',
    'easy_prerequisites',
    'notable_prerequisites',
    'description',
    'notes',
    'comment',
)

_INGREDIENT_FINGERPRINT_FIELDS = (
    'quantity',
    'zone_locations',
    'battlefield_card_state',
    'exile_card_state',
    'graveyard_card_state',
    'library_card_state',
    'must_be_commander',
)


def _hash_parts(parts: Iterable[object]) -> str:
    hasher = hashlib.blake2b(digest_size=16)
    for part in parts:
        hasher.update(repr(part).encode('utf8'))
        hasher.update(b'\x00')
    return hasher.hexdigest()


def _meta_payload() -> dict[str, int]:
    return {
        'version': _FINGERPRINT_VERSION,
        'default_card_limit': DEFAULT_CARD_LIMIT,
        'default_variant_limit': DEFAULT_VARIANT_LIMIT,
        'higher_card_limit': HIGHER_CARD_LIMIT,
        'lower_variant_limit': LOWER_VARIANT_LIMIT,
    }


def compute_fingerprints(data: Data) -> Fingerprints:
    '''
    Computes input fingerprints for every entity involved in variant generation,
    covering everything that can affect generated variants.
    '''
    card_fingerprints = dict[int, str]()
    playable_fields = Playable.playable_fields()
    for card_id, card in data.id_to_card.items():
        feature_of_card_rows = sorted(
            (
                feature_of_card.feature_id,
                *(getattr(feature_of_card, field) for field in _INGREDIENT_FINGERPRINT_FIELDS),
                feature_of_card.mana_needed,
                feature_of_card.easy_prerequisites,
                feature_of_card.notable_prerequisites,
                tuple(sorted(data.feature_of_card_to_attributes.get(feature_of_card.id, ()))),
            )
            for feature_of_card in data.card_to_features.get(card_id, ())
        )
        card_fingerprints[card_id] = _hash_parts((
            tuple(str(getattr(card, field)) for field in playable_fields),
            tuple(getattr(card, field) for field in _CARD_FINGERPRINT_FIELDS),
            feature_of_card_rows,
        ))
    template_fingerprints = {
        template_id: _hash_parts((template.name,))
        for template_id, template in data.id_to_template.items()
    }
    feature_fingerprints = {
        feature_id: _hash_parts((feature.name, feature.status, feature.uncountable))
        for feature_id, feature in data.id_to_feature.items()
    }
    combo_fingerprints = dict[int, str]()
    for combo_id, combo in data.id_to_combo.items():
        card_in_combo_rows = [
            (card_in_combo.card_id, card_in_combo.order, *(getattr(card_in_combo, field) for field in _INGREDIENT_FINGERPRINT_FIELDS))
            for card_in_combo in data.combo_to_cards.get(combo_id, ())
        ]
        template_in_combo_rows = [
            (template_in_combo.template_id, template_in_combo.order, *(getattr(template_in_combo, field) for field in _INGREDIENT_FINGERPRINT_FIELDS))
            for template_in_combo in data.combo_to_templates.get(combo_id, ())
        ]
        feature_needed_in_combo_rows = sorted(
            (
                feature_needed_in_combo.feature_id,
                feature_needed_in_combo.quantity,
                feature_needed_in_combo.zone_locations,
                tuple(sorted(data.feature_needed_in_combo_to_attributes_matcher[feature_needed_in_combo.id].any_of)),
                tuple(sorted(data.feature_needed_in_combo_to_attributes_matcher[feature_needed_in_combo.id].all_of)),
                tuple(sorted(data.feature_needed_in_combo_to_attributes_matcher[feature_needed_in_combo.id].none_of)),
            )
            for feature_needed_in_combo in data.combo_to_needed_features.get(combo_id, ())
        )
        feature_produced_in_combo_rows = sorted(
            (
                feature_produced_in_combo.feature_id,
                tuple(sorted(data.feature_produced_in_combo_to_attributes.get(feature_produced_in_combo.id, ()))),
            )
            for feature_produced_in_combo in data.combo_to_produced_features.get(combo_id, ())
        )
        feature_removed_in_combo_rows = sorted(feature_removed_in_combo.feature_id for feature_removed_in_combo in data.combo_to_removed_features.get(combo_id, ()))
        combo_fingerprints[combo_id] = _hash_parts((
            tuple(getattr(combo, field) for field in _COMBO_FINGERPRINT_FIELDS),
            card_in_combo_rows,
            template_in_combo_rows,
            feature_needed_in_combo_rows,
            feature_produced_in_combo_rows,
            feature_removed_in_combo_rows,
        ))
    return {
        'card': card_fingerprints,
        'template': template_fingerprints,
        'feature': feature_fingerprints,
        'combo': combo_fingerprints,
    }


def load_stored_fingerprints() -> Fingerprints | None:
    '''
    Loads the fingerprints stored by the last successful generation.
    Returns None when they are missing or were computed with an incompatible
    algorithm version or generation limits.
    '''
    rows = {row.kind: row.fingerprints for row in VariantGenerationFingerprints.objects.all()}
    if rows.get(_META_KIND) != _meta_payload():
        return None
    result = dict[str, dict[int, str]]()
    for kind in _ENTITY_KINDS:
        payload = rows.get(kind)
        if payload is None:
            return None
        result[kind] = {int(key): value for key, value in payload.items()}
    return result


def store_fingerprints(fingerprints: Fingerprints) -> None:
    '''Persists the given fingerprints, writing only the rows that changed.'''
    payloads: dict[str, dict[str, str] | dict[str, int]] = {
        kind: {str(key): value for key, value in fingerprints[kind].items()}
        for kind in _ENTITY_KINDS
    }
    payloads[_META_KIND] = _meta_payload()
    existing = {row.kind: row for row in VariantGenerationFingerprints.objects.all()}
    to_create = list[VariantGenerationFingerprints]()
    to_update = list[VariantGenerationFingerprints]()
    for kind, payload in payloads.items():
        row = existing.get(kind)
        if row is None:
            to_create.append(VariantGenerationFingerprints(kind=kind, fingerprints=payload))
        elif row.fingerprints != payload:
            row.fingerprints = payload
            row.updated = timezone.now()
            to_update.append(row)
    if to_create:
        VariantGenerationFingerprints.objects.bulk_create(to_create)
    if to_update:
        VariantGenerationFingerprints.objects.bulk_update(to_update, fields=['fingerprints', 'updated'])


class GenerationScope(Enum):
    FULL = 'full'
    INCREMENTAL = 'incremental'
    SINGLE = 'single'


@dataclass(frozen=True)
class GenerationPlan:
    scope: GenerationScope
    combos_to_generate: list[Combo]
    # All the combo ids whose variants are being regenerated, including combos
    # that are no longer generators (demoted or deleted), used to preserve
    # untouched "variant of combo" relationships and to compute deletions.
    regenerated_combo_ids: set[int]
    fallback_reason: str | None = None


def plan_full_generation(data: Data, reason: str | None = None) -> GenerationPlan:
    return GenerationPlan(
        scope=GenerationScope.FULL,
        combos_to_generate=list(data.generator_combos),
        regenerated_combo_ids={combo.id for combo in data.id_to_combo.values()},
        fallback_reason=reason,
    )


def plan_incremental_generation(data: Data, current: Fingerprints, stored: Fingerprints | None) -> GenerationPlan:
    '''
    Computes the minimal set of generator combos whose variants have to be regenerated,
    given the difference between the current and the stored entity fingerprints.
    Falls back to a full generation plan when a safe incremental plan cannot be computed.
    '''
    if stored is None:
        return plan_full_generation(data, 'no stored fingerprints from a previous generation')
    for variant_id, of_rows in data.variant_to_of_sets.items():
        if not of_rows:
            return plan_full_generation(data, f'variant {variant_id} has no generator combos')
    dirty = dict[str, set[int]]()
    for kind in _ENTITY_KINDS:
        current_kind = current[kind]
        stored_kind = stored[kind]
        removed = stored_kind.keys() - current_kind.keys()
        if removed:
            # Deleting an entity cascades away the very relationships needed
            # to find the affected variants, so a safe incremental plan
            # cannot be computed anymore
            return plan_full_generation(data, f'{len(removed)} {kind} entities were deleted since the last generation')
        dirty[kind] = {
            entity_id
            for entity_id in current_kind.keys() | stored_kind.keys()
            if current_kind.get(entity_id) != stored_kind.get(entity_id)
        }
    if not any(dirty.values()):
        return GenerationPlan(scope=GenerationScope.INCREMENTAL, combos_to_generate=[], regenerated_combo_ids=set())
    # Reverse indexes
    combos_using_card = dict[int, set[int]]()
    combos_using_template = dict[int, set[int]]()
    combos_needing_feature = dict[int, set[int]]()
    combos_producing_feature = dict[int, set[int]]()
    for combo_id in data.id_to_combo:
        for card_in_combo in data.combo_to_cards.get(combo_id, ()):
            combos_using_card.setdefault(card_in_combo.card_id, set()).add(combo_id)
        for template_in_combo in data.combo_to_templates.get(combo_id, ()):
            combos_using_template.setdefault(template_in_combo.template_id, set()).add(combo_id)
        for feature_needed_in_combo in data.combo_to_needed_features.get(combo_id, ()):
            combos_needing_feature.setdefault(feature_needed_in_combo.feature_id, set()).add(combo_id)
        for feature_produced_in_combo in data.combo_to_produced_features.get(combo_id, ()):
            combos_producing_feature.setdefault(feature_produced_in_combo.feature_id, set()).add(combo_id)
    empty_variant_set = set[str]()
    variants_using_card = dict[int, set[str]]()
    for card_id, variant_id in data.variant_uses_card_dict:
        variants_using_card.setdefault(card_id, set()).add(variant_id)
    variants_requiring_template = dict[int, set[str]]()
    for template_id, variant_id in data.variant_requires_template_dict:
        variants_requiring_template.setdefault(template_id, set()).add(variant_id)
    variants_producing_feature = dict[int, set[str]]()
    for feature_id, variant_id in data.variant_produces_feature_dict:
        variants_producing_feature.setdefault(feature_id, set()).add(variant_id)
    variants_including_combo = dict[int, set[str]]()
    for combo_id, variant_id in data.variant_includes_combo_dict:
        variants_including_combo.setdefault(combo_id, set()).add(variant_id)
    # Seed the dirty combos set
    dirty_combos = set(dirty['combo'])
    for card_id in dirty['card']:
        dirty_combos |= combos_using_card.get(card_id, set())
        for feature_of_card in data.card_to_features.get(card_id, ()):
            dirty_combos |= combos_needing_feature.get(feature_of_card.feature_id, set())
    for template_id in dirty['template']:
        dirty_combos |= combos_using_template.get(template_id, set())
    for feature_id in dirty['feature']:
        dirty_combos |= combos_needing_feature.get(feature_id, set())
        dirty_combos |= combos_producing_feature.get(feature_id, set())
    # Expand upward: combos needing features produced by dirty combos are dirty too
    queue = deque(dirty_combos)
    while queue:
        combo_id = queue.popleft()
        for feature_produced_in_combo in data.combo_to_produced_features.get(combo_id, ()):
            for other_combo_id in combos_needing_feature.get(feature_produced_in_combo.feature_id, ()):
                if other_combo_id not in dirty_combos:
                    dirty_combos.add(other_combo_id)
                    queue.append(other_combo_id)
    # Compute the affected variants
    affected_variants = set[str]()
    for combo_id in dirty_combos:
        affected_variants |= variants_including_combo.get(combo_id, empty_variant_set)
    for card_id in dirty['card']:
        affected_variants |= variants_using_card.get(card_id, empty_variant_set)
    for template_id in dirty['template']:
        affected_variants |= variants_requiring_template.get(template_id, empty_variant_set)
    for feature_id in dirty['feature']:
        # Also cover features whose produced-by links may not exist yet or anymore,
        # e.g. when a feature switches between utility and non-utility status
        affected_variants |= variants_producing_feature.get(feature_id, empty_variant_set)
        for combo_id in combos_producing_feature.get(feature_id, ()):
            affected_variants |= variants_including_combo.get(combo_id, empty_variant_set)
        for feature_of_card in data.features_to_cards.get(feature_id, ()):
            affected_variants |= variants_using_card.get(feature_of_card.card_id, empty_variant_set)
    # Variants that could newly match a dirty combo have to be regenerated as well
    for combo_id in dirty_combos:
        # Every dirty combo id comes from the loaded snapshot, so it is always present
        combo = data.id_to_combo[combo_id]
        if combo.status not in (Combo.Status.GENERATOR, Combo.Status.UTILITY):
            continue
        candidate_sets = [
            variants_using_card.get(card_in_combo.card_id, empty_variant_set)
            for card_in_combo in data.combo_to_cards.get(combo_id, ())
        ] + [
            variants_requiring_template.get(template_in_combo.template_id, empty_variant_set)
            for template_in_combo in data.combo_to_templates.get(combo_id, ())
        ] + [
            variants_producing_feature.get(feature_needed_in_combo.feature_id, empty_variant_set)
            for feature_needed_in_combo in data.combo_to_needed_features.get(combo_id, ())
        ]
        if not candidate_sets:
            return plan_full_generation(data, f'dirty combo {combo_id} has no requirements')
        affected_variants |= min(candidate_sets, key=len)
    # Variants flagged for restore have to be regenerated
    for variant_id, variant in data.id_to_variant.items():
        if variant.status == Variant.Status.RESTORE:
            affected_variants.add(variant_id)
    # Every generator combo of an affected variant has to be regenerated,
    # so that all of the affected variants' definitions are recomputed
    regenerated = set(dirty_combos)
    for variant_id in affected_variants:
        for of_row in data.variant_to_of_sets.get(variant_id, ()):
            regenerated.add(of_row.combo_id)
    combos_to_generate = [
        data.id_to_combo[combo_id]
        for combo_id in sorted(regenerated)
        if combo_id in data.id_to_combo and data.id_to_combo[combo_id].status == Combo.Status.GENERATOR
    ]
    return GenerationPlan(
        scope=GenerationScope.INCREMENTAL,
        combos_to_generate=combos_to_generate,
        regenerated_combo_ids=regenerated,
    )
