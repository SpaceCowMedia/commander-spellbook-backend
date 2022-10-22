from enum import Enum
import json
import hashlib
import logging
from typing import Iterable
from dataclasses import dataclass, replace, field
from django.db import transaction
from .models import Card, Feature, Combo, Job, Template, Variant

MAX_CARDS_IN_COMBO = 5


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


@dataclass
class CardNode:
    card: Card
    state: NodeState = NodeState.NOT_VISITED

    def __hash__(self):
        return hash(self.card)


@dataclass
class TemplateNode:
    template: Template
    state: NodeState = NodeState.NOT_VISITED

    def __hash__(self):
        return hash(self.template)


@dataclass
class FeatureNode:
    feature: Feature
    cards: list[CardNode]
    combos: list['ComboNode']
    state: NodeState = NodeState.NOT_VISITED

    def __hash__(self):
        return hash(self.feature)


@dataclass
class ComboNode:
    combo: Combo
    cards: list[CardNode]
    features: list[FeatureNode]
    templates: list[Template]
    state: NodeState = NodeState.NOT_VISITED

    def __hash__(self):
        return hash(self.combo)


@dataclass(frozen=True)
class VariantIngredients:
    cards: list[CardNode]
    templates: list[TemplateNode]
    combos: list[ComboNode]
    of: list[ComboNode] = field(default_factory=list)


@dataclass
class VariantDefinition:
    card_ids: list[int]
    template_ids: set[int]
    of_ids: set[int]
    feature_ids: set[int]
    included_ids: set[int]


class Data:
    def __init__(self):
        self.combos = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces')
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.variants = Variant.objects.prefetch_related('uses', 'requires')
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.templates = Template.objects.prefetch_related('required_by_combos')


class Graph:
    def __init__(self, data: Data = None, other: 'Graph' = None):
        if data is not None and other is None:
            self.data = data
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card)) for card in data.cards)
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template)) for template in data.templates)
            self.fnodes = dict[int, FeatureNode]((feature.id, FeatureNode(feature, [self.cnodes[i.id] for i in feature.cards.all()], [])) for feature in data.features)
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                node = ComboNode(combo, [self.cnodes[i.id] for i in combo.uses.all()], [self.fnodes[i.id] for i in combo.needs.all()], [self.tnodes[i.id] for i in combo.requires.all()])
                self.bnodes[combo.id] = node
                for featureNode in node.features:
                    featureNode.combos.append(node)
        elif data is None and other is not None:
            self.data = other.data
            self.cnodes = {k: replace(v, state=NodeState.NOT_VISITED) for k, v in other.cnodes.items()}
            self.tnodes = {k: replace(v, state=NodeState.NOT_VISITED) for k, v in other.tnodes.items()}
            self.fnodes = {k: replace(v, state=NodeState.NOT_VISITED) for k, v in other.fnodes.items()}
            self.bnodes = {k: replace(v, state=NodeState.NOT_VISITED) for k, v in other.bnodes.items()}
        else:
            raise Exception('Invalid arguments')
    
    def reset(self) -> 'Graph':
        return Graph(other=self)
    
    def variants(self, combo_id: int) -> list[VariantIngredients]:
        combo = self.bnodes[combo_id]
        return self._variantsb(combo)
    
    def _variantsb(self, combo: ComboNode) -> list[VariantIngredients]:
        if combo.state == NodeState.VISITED or combo.state == NodeState.VISITING:
            return []
        combo.state=NodeState.VISITING
        cards = combo.cards
        for c in cards:
            c.state = NodeState.VISITED
        templates = combo.templates
        for t in templates:
            t.state = NodeState.VISITED
        needed_features = combo.features
        cards_amount = len(cards) + len(templates)
        for f in needed_features:
            variantsf = self._variantsf(f, cards_amount)
            if len(variantsf) == 0:
                return []
            pass # TODO implement
        return [VariantIngredients(cards, templates, [combo], [combo])]
            
    
    def _variantsf(self, feature: FeatureNode, base_cards_amount: int = 0) -> list[VariantIngredients]:
        if feature.state == NodeState.VISITED or feature.state == NodeState.VISITING:
            return []
        feature.state=NodeState.VISITING
        cards = feature.cards
        combos = feature.combos
        for c in cards:
            if c.state == NodeState.VISITED or c.state == NodeState.VISITING:
                return [VariantIngredients([], [], [])]
        for c in combos:
            if c.state == NodeState.VISITED or c.state == NodeState.VISITING:
                return [VariantIngredients([], [], [])]
        for c in cards:
            pass
        return []


def unique_id_from_cards_and_templates_ids(cards: list[int], templates: list[int]) -> str:
    hash_algorithm = hashlib.sha256()
    hash_algorithm.update(json.dumps({'c': sorted(cards), 't': sorted(templates)}).encode('utf-8'))
    return hash_algorithm.hexdigest()


def removed_features(variant: Variant, features: set[int]) -> set[int]:
    return features - set(variant.includes.values_list('removes__id', flat=True))


def merge_identities(identities: Iterable[str]):
    i = set(''.join(identities).upper())
    return ''.join([color for color in 'WUBRG' if color in i])


def update_variant(
        data: Data,
        unique_id: str,
        combos_that_generated: set[int],
        combos_included: set[int],
        features: set[int],
        ok: bool,
        restore=False):
    variant = data.variants.get(unique_id=unique_id)
    if combos_that_generated is not None:
        variant.of.set(combos_that_generated)
    variant.includes.set(combos_included)
    variant.produces.set(removed_features(variant, features) - data.utility_features_ids)
    variant.identity = merge_identities(variant.uses.values_list('identity', flat=True))
    if restore:
        combos = data.combos.filter(id__in=combos_included)
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
        cards: list[int],
        templates: set[int],
        combos_that_generated: set[int],
        combos_included: set[int],
        features: set[int],
        ok: bool):
    combos = data.combos.filter(id__in=combos_included)
    zone_locations = '\n'.join(c.zone_locations for c in combos if len(c.zone_locations) > 0)
    cards_state = '\n'.join(c.cards_state for c in combos if len(c.cards_state) > 0)
    other_prerequisites = '\n'.join(c.other_prerequisites for c in combos if len(c.other_prerequisites) > 0)
    mana_needed = ' '.join(c.mana_needed for c in combos if len(c.mana_needed) > 0)
    description = '\n'.join(c.description for c in combos if len(c.description) > 0)
    variant = Variant(
        unique_id=unique_id,
        zone_locations=zone_locations,
        cards_state=cards_state,
        other_prerequisites=other_prerequisites,
        mana_needed=mana_needed,
        description=description,
        identity=merge_identities(data.cards.filter(id__in=cards).values_list('identity', flat=True)))
    if not ok:
        variant.status = Variant.Status.NOT_WORKING
    variant.save()
    variant.uses.set(cards)
    variant.requires.set(templates)
    if combos_that_generated is not None:
        variant.of.set(combos_that_generated)
    variant.includes.set(combos_included)
    variant.produces.set(removed_features(variant, features) - data.utility_features_ids)
    return variant.id


def get_variants_from_graph(data: Data) -> dict[str, VariantDefinition]:
    logging.info('Computing all possible variants')
    combos = data.combos.filter(generator=True)
    result = dict[str, VariantDefinition]()
    for combo in combos:
        graph = Graph(data)
        variants = graph.variants(combo.id)
        for variant in variants:
            cards_ids = [cn.card.id for cn in variant.cards]
            templates_ids = [tn.template.id for tn in variant.templates]
            unique_id = unique_id_from_cards_and_templates_ids(cards_ids, templates_ids)
            if unique_id in result:
                result[unique_id].of_ids.add(combo.id)
            else:
                result[unique_id] = VariantDefinition(
                    card_ids=cards_ids,
                    template_ids=frozenset(templates_ids),
                    feature_ids={f.id for cn in variant.combos for f in cn.combo.produces.all()},
                    included_ids={cn.combo.id for cn in variant.combos},
                    of_ids={combo.id})
    return result


def generate_variants(job: Job = None) -> tuple[int, int, int]:
    logging.info('Fetching variants set to RESTORE...')
    data = Data()
    to_restore = set(data.variants.filter(status=Variant.Status.RESTORE).values_list('unique_id', flat=True))
    logging.info('Fetching all variant unique ids...')
    old_id_set = set(data.variants.values_list('unique_id', flat=True))
    logging.info('Computing combos MILP representation...')
    variants = get_variants_from_graph(data)
    logging.info(f'Saving {len(variants)} variants...')
    if job:
        with transaction.atomic(durable=True):
            job.message += f'Saving {len(variants)} variants...\n'
            job.save()
    variants_ids = set()
    with transaction.atomic():
        for unique_id, variant_def in variants.items():
            if unique_id in old_id_set:
                status = data.variants.get(unique_id=unique_id).status
                update_variant(
                    data=data,
                    unique_id=unique_id,
                    combos_that_generated=variant_def.of_ids,
                    combos_included=variant_def.included_ids,
                    features=variant_def.feature_ids,
                    ok=status is Variant.Status.OK or status is not Variant.Status.NOT_WORKING and True, # TODO: check if variant is valid
                    restore=unique_id in to_restore)
            else:
                variants_ids.add(
                    create_variant(
                        data=data,
                        unique_id=unique_id,
                        cards=variant_def.card_ids,
                        templates=variant_def.template_ids,
                        combos_that_generated=variant_def.of_ids,
                        combos_included=variant_def.included_ids,
                        features=variant_def.feature_ids,
                        ok=True)) # TODO check if variant is valid
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
        return len(added), len(restored), deleted
