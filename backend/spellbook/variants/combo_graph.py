from math import prod
from collections import deque, defaultdict
from typing import Iterable, Callable
from enum import Enum
from dataclasses import dataclass
from spellbook.models.card import Card
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo
from spellbook.models.template import Template
from .variant_data import Data
from .variant_set import VariantSet


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    def __init__(self):
        self.state: NodeState = NodeState.NOT_VISITED
        self.variant_set: VariantSet | None = None

    def __str__(self) -> str:
        return f'{self.__class__} of {self._item()}'

    def _item(self):
        return None


class CardNode(Node):
    def __init__(self, card: Card, features: Iterable['FeatureNode'] = [], combos: Iterable['ComboNode'] = []):
        super().__init__()
        self.card = card
        self.features = list(features)
        self.combos = list(combos)

    def __hash__(self):
        return hash(self.card) + 7 * hash('card')

    def _item(self):
        return self.card


class TemplateNode(Node):
    def __init__(self, template: Template, combos: Iterable['ComboNode'] = []):
        super().__init__()
        self.template = template
        self.combos = list(combos)

    def __hash__(self):
        return hash(self.template) + 7 * hash('template')

    def _item(self):
        return self.template


class FeatureNode(Node):
    def __init__(self, feature: Feature, cards: Iterable[CardNode] = [], produced_by_combos: Iterable['ComboNode'] = [], needed_by_combos: Iterable['ComboNode'] = []):
        super().__init__()
        self.feature = feature
        self.cards = list[CardNode](cards)
        self.produced_by_combos = list(produced_by_combos)
        self.needed_by_combos = list(needed_by_combos)

    def __hash__(self):
        return hash(self.feature) + 7 * hash('feature')

    def _item(self):
        return self.feature


class ComboNode(Node):
    def __init__(self, combo: Combo, cards: Iterable[CardNode] = [], templates: Iterable[TemplateNode] = [], features_needed: Iterable[FeatureNode] = [], features_produced: Iterable[FeatureNode] = []):
        super().__init__()
        self.combo = combo
        self.cards = list(cards)
        self.templates = list(templates)
        self.features_needed = list(features_needed)
        self.features_produced = list(features_produced)

    def __hash__(self):
        return hash(self.combo) + 7 * hash('combo')

    def _item(self):
        return self.combo


@dataclass(frozen=True)
class VariantIngredients:
    cards: list[int]
    templates: list[int]


@dataclass(frozen=True)
class VariantRecipe(VariantIngredients):
    features: list[int]
    combos: list[int]
    replacements: dict[int, list[VariantIngredients]]


class Graph:
    class GraphError(Exception):
        pass

    def __init__(self, data: Data, log=None, card_limit=5, variant_limit=10000):
        if data is not None:
            self.logger: Callable[[str], None] = log if log is not None else lambda msg: self._error(msg)
            self.data = data
            self.card_limit = card_limit
            self.variant_limit = variant_limit
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card, [], [])) for card in data.cards)
            for c in self.cnodes.values():
                c.variant_set = VariantSet(limit=card_limit)
                c.variant_set.add([c.card.id], [])
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template, [])) for template in data.templates)
            for t in self.tnodes.values():
                t.variant_set = VariantSet(limit=card_limit)
                t.variant_set.add([], [t.template.id])
            self.fnodes = dict[int, FeatureNode]()
            for feature in data.features:
                node = FeatureNode(feature,
                    cards=[self.cnodes[i.id] for i in feature.cards.all()],
                    produced_by_combos=[],
                    needed_by_combos=[])
                self.fnodes[feature.id] = node
                for card in feature.cards.all():
                    self.cnodes[card.id].features.append(node)
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                node = ComboNode(combo,
                    cards=[self.cnodes[i.id] for i in combo.uses.all()],
                    templates=[self.tnodes[i.id] for i in combo.requires.all()],
                    features_needed=[self.fnodes[i.id] for i in combo.needs.all()],
                    features_produced=[self.fnodes[i.id] for i in combo.produces.all()])
                self.bnodes[combo.id] = node
                for feature in combo.produces.all():
                    featureNode = self.fnodes[feature.id]
                    featureNode.produced_by_combos.append(node)
                for feature in combo.needs.all():
                    featureNode = self.fnodes[feature.id]
                    featureNode.needed_by_combos.append(node)
                for card in combo.uses.all():
                    self.cnodes[card.id].combos.append(node)
                for template in combo.requires.all():
                    self.tnodes[template.id].combos.append(node)
            self.to_reset_nodes = set[Node]()
        else:
            self._error('Invalid arguments')

    def _error(self, msg: str):
        raise Exception(msg)

    def _reset(self):
        for node in self.to_reset_nodes:
            node.state = NodeState.NOT_VISITED
        self.to_reset_nodes.clear()

    def variants(self, combo_id: int) -> list[VariantRecipe]:
        combo = self.bnodes[combo_id]
        # Reset step
        self._reset()
        # Down step
        variant_set = self._combo_nodes_down(combo)
        # Up steps
        result = list[VariantRecipe]()
        for cards, templates in variant_set.variants():
            self._reset()
            result.append(self._card_nodes_up([self.cnodes[i] for i in cards], [self.tnodes[i] for i in templates]))
        return result

    def _combo_nodes_down(self, combo: ComboNode) -> VariantSet:
        if combo.variant_set is not None:
            combo.state = NodeState.VISITED
            self.to_reset_nodes.add(combo)
            return combo.variant_set
        combo.state = NodeState.VISITING
        self.to_reset_nodes.add(combo)
        card_variant_sets = [c.variant_set for c in combo.cards]
        template_variant_sets = [t.variant_set for t in combo.templates]
        needed_features_variant_sets: list[VariantSet] = []
        for f in combo.features_needed:
            if f.state == NodeState.VISITING:
                return VariantSet(limit=self.card_limit)
            needed_features_variant_sets.append(self._feature_nodes_down(f))
        variant_sets: list[VariantSet] = card_variant_sets + template_variant_sets + needed_features_variant_sets  # type: ignore
        variants_count_proxy = prod(len(vs) for vs in variant_sets)
        if variants_count_proxy > self.variant_limit:
            msg = f'Combo {combo.combo} has too many variants, approx. {variants_count_proxy}'
            self.logger(msg)
            raise Graph.GraphError(msg)
        combo.variant_set = VariantSet.and_sets(variant_sets, limit=self.card_limit)
        combo.state = NodeState.VISITED
        return combo.variant_set

    def _feature_nodes_down(self, feature: FeatureNode) -> VariantSet:
        if feature.variant_set is not None:
            feature.state = NodeState.VISITED
            self.to_reset_nodes.add(feature)
            return feature.variant_set
        feature.state = NodeState.VISITING
        self.to_reset_nodes.add(feature)
        card_variant_sets = [c.variant_set for c in feature.cards]
        produced_combos_variant_sets: list[VariantSet] = []
        for c in feature.produced_by_combos:
            if c.state == NodeState.VISITING:
                continue
            produced_combos_variant_sets.append(self._combo_nodes_down(c))
        variant_sets: list[VariantSet] = card_variant_sets + produced_combos_variant_sets  # type: ignore
        variants_count_proxy = sum(len(vs) for vs in variant_sets)
        if variants_count_proxy > self.variant_limit:
            msg = f'Feature "{feature.feature}" has too many variants, approx. {variants_count_proxy}'
            self.logger(msg)
            raise Graph.GraphError(msg)
        feature.variant_set = VariantSet.or_sets(variant_sets, limit=self.card_limit)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _card_nodes_up(self, cards: list[CardNode], templates: list[TemplateNode]) -> VariantRecipe:
        for ingredient_node in templates + cards:
            ingredient_node.state = NodeState.VISITED
            self.to_reset_nodes.add(ingredient_node)
        card_ids = [c.card.id for c in cards]
        template_ids = [t.template.id for t in templates]
        card_nodes = set(cards)
        template_nodes = set(templates)
        feature_nodes: set[FeatureNode] = set()
        combo_nodes_to_visit: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_features: deque[ComboNode] = deque()
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[int, list[VariantIngredients]](list)
        for card in cards:
            for combo in card.combos:
                if combo.state == NodeState.NOT_VISITED:
                    combo.state = NodeState.VISITING
                    self.to_reset_nodes.add(combo)
                    combo_nodes_to_visit.append(combo)
            for feature in card.features:
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    self.to_reset_nodes.add(feature)
                    feature_nodes.add(feature)
                    replacements[feature.feature.id].append(VariantIngredients([card.card.id], []))
                    for feature_combo in feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            feature_combo.state = NodeState.VISITING
                            self.to_reset_nodes.add(feature_combo)
                            combo_nodes_to_visit.append(feature_combo)
        while combo_nodes_to_visit:
            combo = combo_nodes_to_visit.popleft()
            satisfied = False
            if combo.variant_set is not None:
                if combo.variant_set.is_satisfied_by(card_ids, template_ids):
                    satisfied = True
                else:
                    continue
            else:
                if any((c not in card_nodes for c in combo.cards)) or any((t not in template_nodes for t in combo.templates)):
                    continue
                if all((f in feature_nodes for f in combo.features_needed)):
                    satisfied = True
            if satisfied:
                combo.state = NodeState.VISITED
                combo_nodes.add(combo)
                for feature in combo.features_produced:
                    if feature.state == NodeState.NOT_VISITED:
                        feature.state = NodeState.VISITED
                        self.to_reset_nodes.add(feature)
                        feature_nodes.add(feature)
                        for feature_combo in feature.needed_by_combos:
                            if feature_combo.state == NodeState.NOT_VISITED:
                                feature_combo.state = NodeState.VISITING
                                self.to_reset_nodes.add(feature_combo)
                                combo_nodes_to_visit.append(feature_combo)
                        combo_nodes_to_visit.extend(combo_nodes_to_visit_with_new_features)
                        combo_nodes_to_visit_with_new_features.clear()
            else:
                combo_nodes_to_visit_with_new_features.append(combo)
        return VariantRecipe(
            cards=[cn.card.id for cn in card_nodes],
            templates=[tn.template.id for tn in template_nodes],
            features=[fn.feature.id for fn in feature_nodes],
            combos=[cn.combo.id for cn in combo_nodes if cn.state == NodeState.VISITED],
            replacements=replacements,
        )
