from enum import Enum
from itertools import product
import json
import hashlib
import logging
from math import comb
from typing import Iterable
from dataclasses import dataclass, replace, field
from django.db import transaction
from .models import Card, Feature, Combo, Job, Template, Variant

MAX_CARDS_IN_COMBO = 5


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    state: NodeState = field(default=NodeState.NOT_VISITED)


@dataclass
class CardNode(Node):
    card: Card

    def __hash__(self):
        return hash(self.card)


@dataclass
class TemplateNode(Node):
    template: Template

    def __hash__(self):
        return hash(self.template)


@dataclass
class FeatureNode(Node):
    feature: Feature
    cards: list[CardNode]
    combos: list['ComboNode']

    def __hash__(self):
        return hash(self.feature)


@dataclass
class ComboNode(Node):
    combo: Combo
    cards: list[CardNode]
    features: list[FeatureNode]
    templates: list[TemplateNode]

    def __hash__(self):
        return hash(self.combo)


@dataclass(frozen=True)
class VariantIngredients:
    cards: list[CardNode]
    templates: list[TemplateNode]
    combos: list[ComboNode]


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
    def __init__(self, data: Data = None):
        if data is not None:
            self.data = data
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card)) for card in data.cards)
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template)) for template in data.templates)
            self.fnodes = dict[int, FeatureNode]((feature.id, FeatureNode(feature, [self.cnodes[i.id] for i in feature.cards.all()], [])) for feature in data.features)
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                node = ComboNode(combo, [self.cnodes[i.id] for i in combo.uses.all()], [self.fnodes[i.id] for i in combo.needs.all()], [self.tnodes[i.id] for i in combo.requires.all()])
                self.bnodes[combo.id] = node
                for feature in combo.produces.all():
                    featureNode = self.fnodes[feature.id]
                    featureNode.combos.append(node)
            self._pop = None
        else:
            raise Exception('Invalid arguments')

    def reset(self) -> bool:
        if self._pop is None:
            return False
        for node in self.cnodes.values():
            node.state = NodeState.NOT_VISITED
        for node in self.tnodes.values():
            node.state = NodeState.NOT_VISITED
        for node in self.fnodes.values():
            node.state = NodeState.NOT_VISITED
        for node in self.bnodes.values():
            node.state = NodeState.NOT_VISITED
        self._pop()
        self._pop = None
        return True

    def variants(self, combo_id: int) -> Iterable[VariantIngredients]:
        combo = self.bnodes[combo_id]
        new_variants = self._variantsb(combo)
        result = []
        result.extend(new_variants)
        while self.reset():
            new_variants = self._variantsb(combo)
            result.extend(new_variants)
        return result

    def _variantsb(self, combo: ComboNode, base_cards_amount: int = 0) -> list[VariantIngredients]:
        combo.state = NodeState.VISITING
        cards = combo.cards.copy()
        for c in cards:
            c.state = NodeState.VISITED
        templates = combo.templates.copy()
        for t in templates:
            t.state = NodeState.VISITED
        cards_amount = len(cards) + len(templates) + base_cards_amount
        if cards_amount > MAX_CARDS_IN_COMBO:
            return []
        needed_features = combo.features
        if len(needed_features) == 0:
            return [VariantIngredients(cards, templates, [combo])]
        for f in needed_features:
            variantsf = self._variantsf(f, cards_amount)
            if len(variantsf) == 0:
                return []
            cards.extend(variantsf[0].cards)
            templates.extend(variantsf[0].templates)
            f.state = NodeState.VISITED
        return [VariantIngredients(cards, templates, [combo])]

    def _variantsf(self, feature: FeatureNode, base_cards_amount: int = 0) -> list[VariantIngredients]:
        feature.state = NodeState.VISITING
        cards = feature.cards
        combos = feature.combos
        for c in cards:
            if c.state == NodeState.VISITED:
                return [VariantIngredients([], [], [])]
        for c in combos:
            if c.state == NodeState.VISITED:
                return [VariantIngredients([], [], [])]
        if len(cards) > 0:
            c = cards[0]
            c.state = NodeState.VISITED
            self._pop = lambda: cards.pop(0)
            return [VariantIngredients([c], [], [])]
        for i, c in enumerate(combos):
            if c.state != NodeState.VISITING:
                r = self._variantsb(c, base_cards_amount)
                c.state = NodeState.VISITED
                if len(r) > 0:
                    self._pop = lambda: combos.pop(i)
                    return r
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
                x = result[unique_id]
                x.of_ids.add(combo.id)
                x.included_ids.update({cn.combo.id for cn in variant.combos})
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
                    ok=status is Variant.Status.OK or status is not Variant.Status.NOT_WORKING and True,  # TODO: check if variant is valid
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
                        ok=True))  # TODO check if variant is valid
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
