from typing import Mapping, Iterable, Callable
from math import prod
from collections import deque, defaultdict
from multiset import FrozenMultiset
from itertools import chain, repeat
from enum import Enum
from dataclasses import dataclass
from spellbook.models.card import Card
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo
from spellbook.models.template import Template
from .variant_data import Data
from .variant_set import VariantSet
from .utils import count_contains


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    def __init__(self, graph: 'Graph'):
        self._state = NodeState.NOT_VISITED
        self._filtered_state = NodeState.NOT_VISITED
        self._variant_set: VariantSet | None = None
        self._filtered_variant_set: VariantSet | None = None
        self._graph = graph

    @property
    def state(self) -> NodeState:
        return self._state if self._graph.filter is None else self._filtered_state

    @state.setter
    def state(self, value: NodeState):
        if self._graph.filter is None:
            self._state = value
            self._graph._to_reset_nodes_state.add(self)
        else:
            self._filtered_state = value
            self._graph._to_reset_nodes_filtered_state.add(self)

    @property
    def variant_set(self) -> VariantSet | None:
        if self._graph.filter is None:
            return self._variant_set
        if self._variant_set is not None and self._filtered_variant_set is None:
            self._filtered_variant_set = self._variant_set.filter(self._graph.filter.cards, self._graph.filter.templates)
            self._graph._to_reset_nodes_filtered_variant_set.add(self)
        return self._filtered_variant_set

    @variant_set.setter
    def variant_set(self, value: VariantSet | None):
        if self._graph.filter is None:
            self._variant_set = value
        else:
            self._filtered_variant_set = value
            self._graph._to_reset_nodes_filtered_variant_set.add(self)

    def __str__(self) -> str:
        return f'{self.__class__} of {self._item()}'

    def __repr__(self) -> str:
        return self.__str__()

    def _item(self):
        return None

    def _reset_state(self):
        self._state = NodeState.NOT_VISITED

    def _reset_filtered_state(self):
        self._filtered_state = NodeState.NOT_VISITED

    def _reset_filtered_variant_set(self):
        self._filtered_variant_set = None


class CardNode(Node):
    def __init__(
            self,
            graph: 'Graph',
            card: Card,
            features: Mapping['FeatureNode', int] = {},
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__(graph)
        self.card = card
        self.features = dict(features)
        self.combos = dict(combos)

    def __hash__(self):
        return hash(self.card) + 31 * hash('card')

    def _item(self):
        return self.card


class TemplateNode(Node):
    def __init__(
            self,
            graph: 'Graph',
            template: Template,
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__(graph)
        self.template = template
        self.combos = dict(combos)

    def __hash__(self):
        return hash(self.template) + 31 * hash('template')

    def _item(self):
        return self.template


class FeatureNode(Node):
    def __init__(
        self,
        graph: 'Graph',
        feature: Feature,
        produced_by_cards: Mapping[CardNode, int] = {},
        produced_by_combos: Iterable['ComboNode'] = [],
        needed_by_combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__(graph)
        self.feature = feature
        self.produced_by_cards = dict(produced_by_cards)
        self.produced_by_combos = list(produced_by_combos)
        self.needed_by_combos = dict(needed_by_combos)

    def __hash__(self):
        return hash(self.feature) + 31 * hash('feature')

    def _item(self):
        return self.feature


class ComboNode(Node):
    def __init__(
            self,
            graph: 'Graph',
            combo: Combo,
            cards: Mapping[CardNode, int] = {},
            templates: Mapping[TemplateNode, int] = {},
            countable_features_needed: Mapping[FeatureNode, int] = {},
            uncountable_features_needed: Iterable[FeatureNode] = [],
            features_produced: Iterable[FeatureNode] = [],
    ):
        super().__init__(graph)
        self.combo = combo
        self.cards = dict(cards)
        self.templates = dict(templates)
        self.countable_features_needed = dict(countable_features_needed)
        self.uncountable_features_needed = list(uncountable_features_needed)
        self.features_produced = list(features_produced)

    def __hash__(self):
        return hash(self.combo) + 31 * hash('combo')

    def _item(self):
        return self.combo


@dataclass(frozen=True)
class VariantIngredients:
    cards: FrozenMultiset
    templates: FrozenMultiset


featureid = int
comboid = int


@dataclass(frozen=True)
class VariantRecipe(VariantIngredients):
    features: FrozenMultiset
    combos: set[comboid]
    replacements: dict[featureid, list[VariantIngredients]]


class Graph:
    class GraphError(Exception):
        pass

    def __init__(self,
            data: Data,
            log=None,
            card_limit=5,
            variant_limit=10000):
        self.logger: Callable[[str], None] = log if log is not None else lambda msg: self._error(msg)
        self.card_limit = card_limit
        self.variant_limit = variant_limit
        self.filter: VariantIngredients | None = None
        if data is not None:
            self.data = data
            # Construct card nodes
            self.cnodes = dict[int, CardNode]((card.id, CardNode(self, card)) for card in data.cards)
            for c in self.cnodes.values():
                c.variant_set = VariantSet(limit=card_limit)
                c.variant_set.add(FrozenMultiset({c.card.id: 1}), FrozenMultiset())
            # Construct template nodes
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(self, template)) for template in data.templates)
            for t in self.tnodes.values():
                t.variant_set = VariantSet(limit=card_limit)
                t.variant_set.add(FrozenMultiset(), FrozenMultiset({t.template.id: 1}))
            # Construct feature nodes
            self.fnodes = dict[int, FeatureNode]()
            for feature in data.features:
                node = FeatureNode(self, feature)
                self.fnodes[feature.id] = node
                for i in feature.featureofcard_set.all():  # type: ignore
                    if i.card_id in self.cnodes:
                        cardNode = self.cnodes[i.card_id]
                        node.produced_by_cards.update({cardNode: i.quantity})
                        cardNode.features.update({node: i.quantity})
            # Construct combo nodes
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                if all(i.card_id in self.cnodes for i in combo.cardincombo_set.all()) and \
                        all(i.template_id in self.tnodes for i in combo.templateincombo_set.all()):
                    node = ComboNode(
                        self,
                        combo,
                        cards={self.cnodes[i.card_id]: i.quantity for i in combo.cardincombo_set.all()},
                        templates={self.tnodes[i.template_id]: i.quantity for i in combo.templateincombo_set.all()},
                        countable_features_needed={self.fnodes[i.feature_id]: i.quantity for i in combo.featureneededincombo_set.all() if not self.fnodes[i.feature_id].feature.uncountable},
                        uncountable_features_needed=[self.fnodes[i.feature_id] for i in combo.featureneededincombo_set.all() if self.fnodes[i.feature_id].feature.uncountable],
                        features_produced=[self.fnodes[i.feature_id] for i in combo.featureproducedincombo_set.all()],
                    )
                    self.bnodes[combo.id] = node
                    for i in combo.featureproducedincombo_set.all():
                        featureNode = self.fnodes[i.feature_id]
                        featureNode.produced_by_combos.append(node)
                    for i in combo.featureneededincombo_set.all():
                        featureNode = self.fnodes[i.feature_id]
                        featureNode.needed_by_combos.update({node: i.quantity})
                    for i in combo.cardincombo_set.all():
                        cardNode = self.cnodes[i.card_id]
                        cardNode.combos.update({node: i.quantity})
                    for i in combo.templateincombo_set.all():
                        templateNode = self.tnodes[i.template_id]
                        templateNode.combos.update({node: i.quantity})
            self._to_reset_nodes_state = set[Node]()
            self._to_reset_nodes_filtered_state = set[Node]()
            self._to_reset_nodes_filtered_variant_set = set[Node]()
        else:
            self._error('Invalid arguments')

    def _error(self, msg: str):
        raise Exception(msg)

    def _reset(self):
        if self.filter is not None:
            for node in self._to_reset_nodes_filtered_state:
                node._reset_filtered_state()
            self._to_reset_nodes_filtered_state.clear()
        else:
            for node in self._to_reset_nodes_state:
                node._reset_state()
            self._to_reset_nodes_state.clear()
            for node in self._to_reset_nodes_filtered_state:
                node._reset_filtered_state()
            self._to_reset_nodes_filtered_state.clear()
            for node in self._to_reset_nodes_filtered_variant_set:
                node._reset_filtered_variant_set()
            self._to_reset_nodes_filtered_variant_set.clear()

    def variants(self, combo_id: int) -> VariantSet:
        combo_node = self.bnodes[combo_id]
        self._reset()
        return self._combo_nodes_down(combo_node)

    def results(self, variant_set: VariantSet) -> list[VariantRecipe]:
        result = list[VariantRecipe]()
        for cards, templates in variant_set.variants():
            self._reset()
            recipe = self._card_nodes_up(VariantIngredients(cards, templates))
            result.append(recipe)
        return result

    def _combo_nodes_down(self, combo: ComboNode) -> VariantSet:
        if combo.variant_set is not None:
            combo.state = NodeState.VISITED
            return combo.variant_set
        combo.state = NodeState.VISITING
        card_variant_sets: list[VariantSet] = []
        for c, q in combo.cards.items():
            variant_set: VariantSet = c.variant_set ** q  # type: ignore
            if self.filter is not None:
                variant_set = variant_set.filter(self.filter.cards, self.filter.templates)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(limit=self.card_limit)
                return combo.variant_set
            card_variant_sets.append(variant_set)
        template_variant_sets: list[VariantSet] = []
        for t, q in combo.templates.items():
            variant_set: VariantSet = t.variant_set ** q  # type: ignore
            if self.filter is not None:
                variant_set = variant_set.filter(self.filter.cards, self.filter.templates)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(limit=self.card_limit)
                return combo.variant_set
            template_variant_sets.append(variant_set)
        needed_features_variant_sets: list[VariantSet] = []
        for f, q in chain(combo.countable_features_needed.items(), zip(combo.uncountable_features_needed, repeat(1))):
            if f.state == NodeState.VISITING:
                return VariantSet(limit=self.card_limit)
            variant_set = self._feature_nodes_down(f)
            variants_count_estimate = len(variant_set) * q
            if variants_count_estimate > self.variant_limit:
                msg = f'{q} x Feature "{f.feature}" has too many variants, approx. {variants_count_estimate}'
                self.logger(msg)
                raise Graph.GraphError(msg)
            variant_set = variant_set ** q
            if self.filter is not None:
                variant_set = variant_set.filter(self.filter.cards, self.filter.templates)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(limit=self.card_limit)
                return combo.variant_set
            needed_features_variant_sets.append(variant_set)
        variant_sets: list[VariantSet] = card_variant_sets + template_variant_sets + needed_features_variant_sets
        variants_count_estimate = prod(len(vs) for vs in variant_sets)
        if variants_count_estimate > self.variant_limit:
            msg = f'Combo {combo.combo} has too many variants, approx. {variants_count_estimate}'
            self.logger(msg)
            raise Graph.GraphError(msg)
        combo.variant_set = VariantSet.and_sets(variant_sets, limit=self.card_limit)
        combo.state = NodeState.VISITED
        return combo.variant_set

    def _feature_nodes_down(self, feature: FeatureNode) -> VariantSet:
        if feature.variant_set is not None:
            feature.state = NodeState.VISITED
            return feature.variant_set
        feature.state = NodeState.VISITING
        card_variant_sets: list[VariantSet] = [c.variant_set ** q for c, q in feature.produced_by_cards.items()]  # type: ignore
        produced_combos_variant_sets: list[VariantSet] = []
        for c in feature.produced_by_combos:
            if c.state == NodeState.VISITING:
                continue
            variant_set = self._combo_nodes_down(c)
            if variant_set:
                produced_combos_variant_sets.append(variant_set)
        variant_sets = card_variant_sets + produced_combos_variant_sets
        variants_count_estimate = sum(len(vs) for vs in variant_sets)
        if variants_count_estimate > self.variant_limit:
            msg = f'Feature "{feature.feature}" has too many variants, approx. {variants_count_estimate}'
            self.logger(msg)
            raise Graph.GraphError(msg)
        feature.variant_set = VariantSet.or_sets(variant_sets, limit=self.card_limit)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _card_nodes_up(self, ingredients: VariantIngredients) -> VariantRecipe:
        cards = {self.cnodes[c]: q for c, q in ingredients.cards.items()}
        templates = {self.tnodes[t]: q for t, q in ingredients.templates.items()}
        for ingredient_node in chain(templates, cards):
            ingredient_node.state = NodeState.VISITED
        countable_feature_nodes = dict[FeatureNode, int]()
        uncountable_feature_nodes = set[FeatureNode]()
        combo_nodes_to_visit: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_countable_features: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_uncountable_features: deque[ComboNode] = deque()
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[int, list[VariantIngredients]](list)
        for card, quantity in cards.items():
            for combo in card.combos:
                if combo.state == NodeState.NOT_VISITED:
                    if all(cards.get(c, 0) >= q for c, q in combo.cards.items()) \
                            and all(templates.get(t, 0) >= q for t, q in combo.templates.items()):
                        combo.state = NodeState.VISITING
                        combo_nodes_to_visit.append(combo)
                    else:
                        combo.state = NodeState.VISITED
            for feature, cards_needed in card.features.items():
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    if feature.feature.uncountable:
                        uncountable_feature_nodes.add(feature)
                        feature_count = 1
                    else:
                        feature_count = quantity // cards_needed
                        countable_feature_nodes[feature] = countable_feature_nodes.get(feature, 0) + feature_count
                    replacements[feature.feature.id].append(
                        VariantIngredients(
                            cards=FrozenMultiset({card.card.id: feature_count * cards_needed}),
                            templates=FrozenMultiset()
                        )
                    )
                    for feature_combo in feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            if all(cards.get(c, 0) >= q for c, q in feature_combo.cards.items()) \
                                    and all(templates.get(t, 0) >= q for t, q in feature_combo.templates.items()):
                                feature_combo.state = NodeState.VISITING
                                combo_nodes_to_visit.append(feature_combo)
                            else:
                                feature_combo.state = NodeState.VISITED
        while combo_nodes_to_visit:
            combo = combo_nodes_to_visit.popleft()
            variant_set = None
            if combo.variant_set is not None:
                variant_set = combo.variant_set
                if not variant_set.is_satisfied_by(ingredients.cards, ingredients.templates):
                    continue
            else:
                if any(q > countable_feature_nodes.get(f, 0) for f, q in combo.countable_features_needed.items()):
                    combo_nodes_to_visit_with_new_countable_features.append(combo)
                    continue
                if any(f not in uncountable_feature_nodes for f in combo.uncountable_features_needed):
                    combo_nodes_to_visit_with_new_uncountable_features.append(combo)
                    continue
                if not all(f.feature.uncountable for f in combo.features_produced):
                    self.filter = ingredients
                    self._reset()
                    variant_set = self._combo_nodes_down(combo)
                    self.filter = None
            combo.state = NodeState.VISITED
            combo_nodes.add(combo)
            if variant_set is not None:
                satisfied_by = variant_set.satisfied_by(ingredients.cards, ingredients.templates)
                replacements_for_combo = [
                    VariantIngredients(cards_satisfying, templates_satisfying)
                    for cards_satisfying, templates_satisfying
                    in satisfied_by
                ]
                quantity = 0
                for cards_satisfying, templates_satisfying in satisfied_by:
                    count_for_cards = count_contains(ingredients.cards, cards_satisfying) if cards_satisfying else None
                    count_for_templates = count_contains(ingredients.templates, templates_satisfying) if templates_satisfying else None
                    if count_for_cards is not None:
                        if count_for_templates is not None:
                            quantity += min(count_for_cards, count_for_templates)
                        else:
                            quantity += count_for_cards
                    elif count_for_templates is not None:
                        quantity += count_for_templates
                for feature in combo.features_produced:
                    if not feature.feature.uncountable:
                        replacements[feature.feature.id].extend(replacements_for_combo)
                        countable_feature_nodes[feature] = countable_feature_nodes.get(feature, 0) + quantity
                        combo_nodes_to_visit.extend(combo_nodes_to_visit_with_new_countable_features)
                        combo_nodes_to_visit_with_new_countable_features.clear()
            for feature in combo.features_produced:
                if feature.feature.uncountable and feature not in uncountable_feature_nodes:
                    uncountable_feature_nodes.add(feature)
                    combo_nodes_to_visit.extend(combo_nodes_to_visit_with_new_uncountable_features)
                    combo_nodes_to_visit_with_new_uncountable_features.clear()
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    for feature_combo in feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            if all(c in cards and cards[c] >= q for c, q in feature_combo.cards.items()) \
                                    and all(t in templates and templates[t] >= q for t, q in feature_combo.templates.items()):
                                feature_combo.state = NodeState.VISITING
                                combo_nodes_to_visit.append(feature_combo)
                            else:
                                feature_combo.state = NodeState.VISITED
        return VariantRecipe(
            cards=ingredients.cards,
            templates=ingredients.templates,
            features=FrozenMultiset({
                f.feature.id: q for f, q in countable_feature_nodes.items()
            } | {
                f.feature.id: 1 for f in uncountable_feature_nodes
            }),
            combos={cn.combo.id for cn in combo_nodes if cn.state == NodeState.VISITED},
            replacements=replacements,
        )
