from typing import Mapping, Iterable, Generic, TypeVar
from math import prod
from collections import deque, defaultdict
from multiset import FrozenMultiset, Multiset
from itertools import chain
from enum import Enum
from dataclasses import dataclass, replace
from spellbook.models import Card, Feature, FeatureOfCard, Combo, Template
from .variant_data import AttributesMatcher, Data
from .variant_set import VariantSet, VariantSetParameters, cardid, templateid
from .utils import count_contains


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


T = TypeVar('T')


class Node(Generic[T]):
    def __init__(self, graph: 'Graph', item: T):
        self._variant_set: VariantSet | None = None
        self._filtered_variant_set: VariantSet | None = None
        self._graph = graph
        self.item = item
        self._hash = hash(item) + 31 * hash(self.__class__.__name__)

    @property
    def variant_set(self) -> VariantSet | None:
        if self._graph.variant_set_parameters.filter is None:
            return self._variant_set
        if self._variant_set is not None and self._filtered_variant_set is None:
            self._filtered_variant_set = self._variant_set.filter(self._graph.variant_set_parameters.filter)
            self._graph._to_reset_nodes_filtered_variant_set.add(self)
        return self._filtered_variant_set

    @variant_set.setter
    def variant_set(self, value: VariantSet | None):
        if self._graph.variant_set_parameters.filter is None:
            self._variant_set = value
        else:
            self._filtered_variant_set = value
            self._graph._to_reset_nodes_filtered_variant_set.add(self)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} of {self.item}'

    def __repr__(self) -> str:
        return self.__str__()

    def _reset_state(self):
        self._state = NodeState.NOT_VISITED

    def _reset_subgraph_state(self):
        self._filtered_state = NodeState.NOT_VISITED

    def _reset_filtered_variant_set(self):
        self._filtered_variant_set = None

    def __hash__(self):
        return self._hash


class NodeWithState(Node[T]):
    def __init__(self, graph: 'Graph', item: T):
        super().__init__(graph, item)
        self._state = NodeState.NOT_VISITED
        self._subgraph_state = NodeState.NOT_VISITED

    @property
    def state(self) -> NodeState:
        return self._subgraph_state if self._graph.subgraph else self._state

    @state.setter
    def state(self, value: NodeState):
        if self._graph.subgraph:
            self._subgraph_state = value
            self._graph._to_reset_nodes_subgraph_state.add(self)
        else:
            self._state = value
            self._graph._to_reset_nodes_state.add(self)


class NodeWithoutState(Node[T]):
    def __init__(self, graph: 'Graph', item: T, variant_set: VariantSet):
        super().__init__(graph, item)
        self._variant_set = variant_set

    @property
    def variant_set(self) -> VariantSet:
        return super().variant_set  # type: ignore


class CardNode(NodeWithoutState[Card]):
    def __init__(
            self,
            graph: 'Graph',
            card: Card,
            features: Iterable['FeatureOfCardNode'] = [],
            combos: Mapping['ComboNode', int] = {},
    ):
        variant_set = VariantSet(
            parameters=graph.variant_set_parameters,
            keys=(VariantSet.ingredients_to_key(FrozenMultiset({card.id: 1}), FrozenMultiset()),),
        )
        super().__init__(graph, card, variant_set)
        self.features = list(features)
        self.combos = dict(combos)


class TemplateNode(NodeWithoutState[Template]):
    def __init__(
            self,
            graph: 'Graph',
            template: Template,
            combos: Mapping['ComboNode', int] = {},
    ):
        variant_set = VariantSet(
            parameters=graph.variant_set_parameters,
            keys=(VariantSet.ingredients_to_key(FrozenMultiset(), FrozenMultiset({template.id: 1})),),
        )
        super().__init__(graph, template, variant_set)
        self.combos = dict(combos)


class FeatureOfCardNode(NodeWithoutState[FeatureOfCard]):
    def __init__(
        self,
        graph: 'Graph',
        feature_of_card: FeatureOfCard,
        quantity: int,
        card: CardNode,
        feature: 'FeatureWithAttributesNode',
    ):
        variant_set = VariantSet.product_sets(
            [card.variant_set] * quantity,
            parameters=graph.variant_set_parameters,
        )
        super().__init__(graph, feature_of_card, variant_set)
        self.quantity = quantity
        self.card = card
        self.feature = feature


@dataclass(frozen=True)
class FeatureWithAttributes:
    feature: Feature
    attributes: frozenset[int]


class FeatureWithAttributesNode(NodeWithState[FeatureWithAttributes]):
    def __init__(
        self,
        graph: 'Graph',
        feature: FeatureWithAttributes,
        produced_by_cards: Iterable[FeatureOfCardNode] = [],
        produced_by_combos: Iterable['ComboNode'] = [],
        matches: Iterable['FeatureWithAttributesMatcherNode'] = [],
    ):
        super().__init__(graph, feature)
        self.produced_by_cards = list(produced_by_cards)
        self.produced_by_combos = list(produced_by_combos)
        self.matches = list(matches)


@dataclass(frozen=True)
class FeatureWithAttributesMatcher:
    feature: Feature
    matcher: AttributesMatcher


class FeatureWithAttributesMatcherNode(NodeWithState[FeatureWithAttributesMatcher]):
    def __init__(
        self,
        graph: 'Graph',
        feature: FeatureWithAttributesMatcher,
        needed_by_combos: Mapping['ComboNode', int] = {},
        matches: Iterable[FeatureWithAttributesNode] = [],
    ):
        super().__init__(graph, feature)
        self.needed_by_combos = dict['ComboNode', int](needed_by_combos)
        self.matches = set(matches)


class ComboNode(NodeWithState[Combo]):
    def __init__(
        self,
        graph: 'Graph',
        combo: Combo,
        cards: Mapping[CardNode, int] = {},
        templates: Mapping[TemplateNode, int] = {},
        countable_features_needed: Mapping[FeatureWithAttributesMatcherNode, int] = {},
        uncountable_features_needed: Iterable[FeatureWithAttributesMatcherNode] = [],
        features_produced: Iterable[FeatureWithAttributesNode] = [],
    ):
        super().__init__(graph, combo)
        self.cards = Multiset[CardNode](cards)
        self.templates = Multiset[TemplateNode](templates)
        self.features_needed = dict[Feature, dict[FeatureWithAttributesMatcherNode, int]]()
        for f, q in countable_features_needed.items():
            self.features_needed.setdefault(f.item.feature, {})[f] = q
        for f in uncountable_features_needed:
            self.features_needed.setdefault(f.item.feature, {})[f] = 1
        self.features_produced = list(features_produced)


@dataclass(frozen=True)
class VariantIngredients:
    cards: FrozenMultiset[cardid]
    templates: FrozenMultiset[templateid]


featureid = int
featureofcardid = int
comboid = int


@dataclass(frozen=True)
class VariantRecipe(VariantIngredients):
    features: FrozenMultiset[featureid]
    combos: set[comboid]
    replacements: dict[FeatureWithAttributes, list[VariantIngredients]]
    needed_feature_of_cards: set[featureofcardid]
    needed_combos: set[comboid]


def satisfies(produced: Iterable[FeatureWithAttributes], needed: Iterable[FeatureWithAttributesMatcher]) -> bool:
    for n in needed:
        if not any(p.feature == n.feature and n.matcher.matches(p.attributes) for p in produced):
            return False
    return True


class Graph:
    class GraphError(Exception):
        pass

    def __init__(self,
            data: Data,
            card_limit=5,
            variant_limit=10000,
            allow_multiple_copies=False):
        self.variant_limit = variant_limit
        self.variant_set_parameters = VariantSetParameters(max_depth=card_limit, allow_multiple_copies=allow_multiple_copies)
        self.subgraph = False
        self.data = data
        # Construct card nodes
        self.card_nodes: dict[cardid, CardNode] = {card_id: CardNode(self, card) for card_id, card in data.id_to_card.items()}
        # Construct feature with attributes nodes
        feature_with_attributes_nodes = dict[featureid, dict[frozenset[int], FeatureWithAttributesNode]]()
        # Iterate over cards
        for card_id, card_node in self.card_nodes.items():
            for feature_of_card in data.card_to_features[card_id]:
                attributes = frozenset(data.feature_of_card_to_attributes[feature_of_card.id])
                feature_with_attributes_node = feature_with_attributes_nodes.setdefault(
                    feature_of_card.feature_id,
                    {},
                ).setdefault(
                    attributes,
                    FeatureWithAttributesNode(
                        self,
                        FeatureWithAttributes(
                            data.id_to_feature[feature_of_card.feature_id],
                            attributes,
                        ),
                    )
                )
                if any(f.feature == feature_with_attributes_node for f in card_node.features):
                    # A card cannot produce the same feature with the same attributes multiple times
                    continue
                feature_of_card_node = FeatureOfCardNode(
                    self,
                    feature_of_card,
                    feature_of_card.quantity,
                    card_node,
                    feature_with_attributes_node,
                )
                card_node.features.append(feature_of_card_node)
                feature_with_attributes_node.produced_by_cards.append(feature_of_card_node)
        # Construct template nodes
        self.template_nodes = {template_id: TemplateNode(self, template) for template_id, template in data.id_to_template.items()}
        # Construct feature with attribute matchers nodes
        feature_attributes_matcher_nodes = dict[featureid, dict[AttributesMatcher, FeatureWithAttributesMatcherNode]]()
        # Construct combo nodes
        self.combo_nodes = dict[comboid, ComboNode]()
        for combo_id, combo in data.id_to_combo.items():
            if combo.status not in (Combo.Status.GENERATOR, Combo.Status.UTILITY):
                continue
            if all(i.card_id in self.card_nodes for i in data.combo_to_cards[combo_id]) \
                    and all(i.template_id in self.template_nodes for i in data.combo_to_templates[combo_id]):
                combo_node = ComboNode(self, combo)
                self.combo_nodes[combo_id] = combo_node
                for card_in_combo in data.combo_to_cards[combo_id]:
                    card_node = self.card_nodes[card_in_combo.card_id]
                    combo_node.cards[card_node] = card_in_combo.quantity
                    card_node.combos[combo_node] = card_in_combo.quantity
                for template_in_combo in data.combo_to_templates[combo_id]:
                    template_node = self.template_nodes[template_in_combo.template_id]
                    combo_node.templates[template_node] = template_in_combo.quantity
                    template_node.combos[combo_node] = template_in_combo.quantity
                for feature_produced_by_combo in data.combo_to_produced_features[combo_id]:
                    attributes = frozenset(data.feature_produced_in_combo_to_attributes[feature_produced_by_combo.id])
                    feature_with_attributes_node = feature_with_attributes_nodes.setdefault(
                        feature_produced_by_combo.feature_id,
                        {},
                    ).setdefault(
                        attributes,
                        FeatureWithAttributesNode(
                            self,
                            FeatureWithAttributes(
                                data.id_to_feature[feature_produced_by_combo.feature_id],
                                attributes,
                            ),
                        )
                    )
                    if any(f == feature_with_attributes_node for f in combo_node.features_produced):
                        # A combo cannot produce the same feature with the same attributes multiple times
                        continue
                    combo_node.features_produced.append(feature_with_attributes_node)
                    feature_with_attributes_node.produced_by_combos.append(combo_node)
                for feature_needed_by_combo in data.combo_to_needed_features[combo.id]:
                    attributes_matcher = data.feature_needed_in_combo_to_attributes_matcher[feature_needed_by_combo.id]
                    feature_with_attributes_matcher_node = feature_attributes_matcher_nodes.setdefault(
                        feature_needed_by_combo.feature_id,
                        {},
                    ).setdefault(
                        attributes_matcher,
                        FeatureWithAttributesMatcherNode(
                            self,
                            FeatureWithAttributesMatcher(
                                data.id_to_feature[feature_needed_by_combo.feature_id],
                                attributes_matcher,
                            ),
                        )
                    )
                    if feature_with_attributes_matcher_node.item.feature.uncountable:
                        combo_node.features_needed.setdefault(feature_with_attributes_matcher_node.item.feature, {})[feature_with_attributes_matcher_node] = 1
                        feature_with_attributes_matcher_node.needed_by_combos[combo_node] = 1
                    else:
                        combo_node.features_needed.setdefault(feature_with_attributes_matcher_node.item.feature, {})[feature_with_attributes_matcher_node] = combo_node.features_needed.get(feature_with_attributes_matcher_node.item.feature, {}).get(feature_with_attributes_matcher_node, 0) + feature_needed_by_combo.quantity
                        feature_with_attributes_matcher_node.needed_by_combos[combo_node] = feature_with_attributes_matcher_node.needed_by_combos.get(combo_node, 0) + feature_needed_by_combo.quantity
        # Find matching feature with attributes nodes
        for feature_id, d in feature_attributes_matcher_nodes.items():
            candidates = feature_with_attributes_nodes.get(feature_id, {})
            for feature_with_attributes_matcher_node in d.values():
                for attributes, matching_node in candidates.items():
                    if feature_with_attributes_matcher_node.item.matcher.matches(attributes):
                        feature_with_attributes_matcher_node.matches.add(matching_node)
                        matching_node.matches.append(feature_with_attributes_matcher_node)
        self._to_reset_nodes_state = set[Node]()
        self._to_reset_nodes_subgraph_state = set[Node]()
        self._to_reset_nodes_filtered_variant_set = set[Node]()

    def _error(self, msg: str):
        raise Exception(msg)

    def _reset(self):
        for node in self._to_reset_nodes_subgraph_state:
            node._reset_subgraph_state()
        self._to_reset_nodes_subgraph_state.clear()
        if self.subgraph:
            return
        for node in self._to_reset_nodes_state:
            node._reset_state()
        self._to_reset_nodes_state.clear()
        for node in self._to_reset_nodes_filtered_variant_set:
            node._reset_filtered_variant_set()
        self._to_reset_nodes_filtered_variant_set.clear()
        self.variant_set_parameters = replace(self.variant_set_parameters, filter=None)

    def variants(self, combo_id: int) -> VariantSet:
        combo_node = self.combo_nodes[combo_id]
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
            variant_set = VariantSet.product_sets([c.variant_set] * q, parameters=self.variant_set_parameters)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(parameters=self.variant_set_parameters)
                return combo.variant_set
            card_variant_sets.append(variant_set)
        template_variant_sets: list[VariantSet] = []
        for t, q in combo.templates.items():
            variant_set = VariantSet.product_sets([t.variant_set] * q, parameters=self.variant_set_parameters)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(parameters=self.variant_set_parameters)
                return combo.variant_set
            template_variant_sets.append(variant_set)
        needed_features_variant_sets: list[VariantSet] = []
        for feature, features_needed in combo.features_needed.items():
            variant_sets = list[VariantSet]()
            for f, q in features_needed.items():
                if f.state == NodeState.VISITING:
                    return VariantSet(parameters=self.variant_set_parameters)
                variant_set = self._feature_with_attribute_matchers_nodes_down(f)
                variant_sets.extend([variant_set] * q)
            variant_count_estimate = sum(len(vs) for vs in variant_sets)
            if variant_count_estimate > self.variant_limit:
                raise Graph.GraphError(f'{len(variant_sets)} x Feature "{feature}" has too many variants, approx. {variant_count_estimate}')
            variant_set = VariantSet.product_sets(variant_sets, parameters=self.variant_set_parameters)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = VariantSet(parameters=self.variant_set_parameters)
                return combo.variant_set
            needed_features_variant_sets.append(variant_set)
        variant_sets: list[VariantSet] = card_variant_sets + template_variant_sets + needed_features_variant_sets
        variant_count_estimate = prod(len(vs) for vs in variant_sets)
        if variant_count_estimate > self.variant_limit:
            raise Graph.GraphError(f'Combo {combo.item} has too many variants, approx. {variant_count_estimate}')
        combo.variant_set = VariantSet.and_sets(variant_sets, parameters=self.variant_set_parameters)
        combo.state = NodeState.VISITED
        return combo.variant_set

    def _feature_with_attribute_matchers_nodes_down(self, feature: FeatureWithAttributesMatcherNode) -> VariantSet:
        if feature.variant_set is not None:
            feature.state = NodeState.VISITED
            return feature.variant_set
        feature.state = NodeState.VISITING
        variant_sets: list[VariantSet] = []
        for m in feature.matches:
            if m.state == NodeState.VISITING:
                continue
            variant_set = self._feature_with_attributes_nodes_down(m)
            if variant_set:
                variant_sets.append(variant_set)
        feature.variant_set = VariantSet.or_sets(variant_sets, parameters=self.variant_set_parameters)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _feature_with_attributes_nodes_down(self, feature: FeatureWithAttributesNode) -> VariantSet:
        if feature.variant_set is not None:
            feature.state = NodeState.VISITED
            return feature.variant_set
        feature.state = NodeState.VISITING
        card_variant_sets: list[VariantSet] = [f.variant_set for f in feature.produced_by_cards]
        produced_combos_variant_sets: list[VariantSet] = []
        for c in feature.produced_by_combos:
            if c.state == NodeState.VISITING:
                continue
            variant_set = self._combo_nodes_down(c)
            if variant_set:
                produced_combos_variant_sets.append(variant_set)
        variant_sets = card_variant_sets + produced_combos_variant_sets
        variant_count_estimate = sum(len(vs) for vs in variant_sets)
        if variant_count_estimate > self.variant_limit:
            raise Graph.GraphError(f'Feature "{feature.item}" has too many variants, approx. {variant_count_estimate}')
        feature.variant_set = VariantSet.or_sets(variant_sets, parameters=self.variant_set_parameters)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _card_nodes_up(self, ingredients: VariantIngredients) -> VariantRecipe:
        self.variant_set_parameters = replace(self.variant_set_parameters, filter=VariantSet.ingredients_to_key(ingredients.cards, ingredients.templates))
        cards = FrozenMultiset[CardNode]({self.card_nodes[c]: q for c, q in ingredients.cards.items()})
        templates = FrozenMultiset[TemplateNode]({self.template_nodes[t]: q for t, q in ingredients.templates.items()})
        feature_of_card_nodes = set[FeatureOfCardNode]()
        countable_feature_nodes = dict[FeatureWithAttributesNode, int]()
        uncountable_feature_nodes = set[FeatureWithAttributesNode]()
        combo_nodes_to_visit: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_countable_features: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_uncountable_features: deque[ComboNode] = deque()
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[FeatureWithAttributes, list[VariantIngredients]](list)
        for ingredient, quantity in chain(cards.items(), templates.items()):
            for combo in ingredient.combos:
                if combo.state == NodeState.NOT_VISITED:
                    if combo.variant_set or cards.issuperset(combo.cards) and templates.issuperset(combo.templates):
                        combo.state = NodeState.VISITING
                        combo_nodes_to_visit.append(combo)
                    else:
                        combo.state = NodeState.VISITED
        for card, quantity in cards.items():
            for feature_of_card in card.features:
                feature_of_card_nodes.add(feature_of_card)
                feature = feature_of_card.feature
                cards_needed = feature_of_card.quantity
                if feature.item.feature.uncountable:
                    feature_count = 1
                    uncountable_feature_nodes.add(feature)
                else:
                    feature_count = quantity // cards_needed
                    countable_feature_nodes[feature] = countable_feature_nodes.get(feature, 0) + feature_count
                replacements[feature.item].append(
                    VariantIngredients(
                        cards=FrozenMultiset({card.item.id: cards_needed}),
                        templates=FrozenMultiset()
                    )
                )
                if feature.state == NodeState.VISITED:
                    continue
                feature.state = NodeState.VISITED
                for matching_feature in feature.matches:
                    for feature_combo in matching_feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            if feature_combo.variant_set or cards.issuperset(feature_combo.cards) and templates.issuperset(feature_combo.templates):
                                feature_combo.state = NodeState.VISITING
                                combo_nodes_to_visit.append(feature_combo)
                            else:
                                feature_combo.state = NodeState.VISITED
        while combo_nodes_to_visit:
            combo = combo_nodes_to_visit.popleft()
            variant_set: VariantSet | None = None
            if combo.variant_set is not None:
                variant_set = combo.variant_set
                if not variant_set:
                    combo.state = NodeState.VISITED
                    continue
            else:
                if not self._check_satisfiability_of_uncountable_features(
                    combo,
                    uncountable_feature_nodes,
                ):
                    combo_nodes_to_visit_with_new_uncountable_features.append(combo)
                    continue
                if not self._check_satisfiability_of_countable_features(
                    combo,
                    countable_feature_nodes,
                ):
                    combo_nodes_to_visit_with_new_countable_features.append(combo)
                    continue
                if not all(f.item.feature.uncountable for f in combo.features_produced):
                    # it makes sense to compute the variant set only if the combo produces countable features
                    # variant set is only used to determine the amount of times the combo is used
                    self.subgraph = True
                    self._reset()
                    variant_set = self._combo_nodes_down(combo)
                    self.subgraph = False
            combo.state = NodeState.VISITED
            combo_nodes.add(combo)
            if variant_set is not None:
                replacements_for_combo = [
                    VariantIngredients(cards_satisfying, templates_satisfying)
                    for cards_satisfying, templates_satisfying
                    in variant_set.variants()
                ]
                quantity = 0
                for cards_satisfying, templates_satisfying in variant_set.variants():
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
                    if not feature.item.feature.uncountable:
                        replacements[feature.item].extend(replacements_for_combo)
                        countable_feature_nodes[feature] = countable_feature_nodes.get(feature, 0) + quantity
                        combo_nodes_to_visit.extend(combo_nodes_to_visit_with_new_countable_features)
                        combo_nodes_to_visit_with_new_countable_features.clear()
            for feature in combo.features_produced:
                if feature.item.feature.uncountable and feature not in uncountable_feature_nodes:
                    uncountable_feature_nodes.add(feature)
                    combo_nodes_to_visit.extend(combo_nodes_to_visit_with_new_uncountable_features)
                    combo_nodes_to_visit_with_new_uncountable_features.clear()
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    for matching_feature in feature.matches:
                        for feature_combo in matching_feature.needed_by_combos:
                            if feature_combo.state == NodeState.NOT_VISITED:
                                if feature_combo.variant_set or cards.issuperset(feature_combo.cards) and templates.issuperset(feature_combo.templates):
                                    feature_combo.state = NodeState.VISITING
                                    combo_nodes_to_visit.append(feature_combo)
                                else:
                                    feature_combo.state = NodeState.VISITED
        # Compute needed features and combos
        interesting_features = set[FeatureWithAttributes](  # by default interesting features are not utility features
            f.item
            for f in chain(countable_feature_nodes.keys(), uncountable_feature_nodes)
            if not f.item.feature.is_utility
        )
        needed_combo_nodes = set[ComboNode](  # by default needed combos produce interesting features
            c
            for c in combo_nodes
            if any(f.item in interesting_features for f in c.features_produced)
        )
        needed_feature_of_card_nodes = set[FeatureOfCardNode](  # by default needed features of cards produce interesting features
            f
            for f in feature_of_card_nodes
            if f.feature.item in interesting_features
        )
        new_features_needed_by_needed_combos = {f.item for c in needed_combo_nodes for features_needed in c.features_needed.values() for f in features_needed}
        while not satisfies(interesting_features, new_features_needed_by_needed_combos):
            new_features_produced_by_needed_combos = {
                fa.item
                for fa in chain(countable_feature_nodes.keys(), uncountable_feature_nodes)
                if any(
                    fam.feature == fa.item.feature and fam.matcher.matches(fa.item.attributes)
                    for fam in new_features_needed_by_needed_combos
                )
            }
            interesting_features.update(new_features_produced_by_needed_combos)
            new_needed_combos = {c for c in combo_nodes if any(f.item in new_features_produced_by_needed_combos for f in c.features_produced)}
            needed_combo_nodes.update(new_needed_combos)
            new_feature_of_card_nodes = {f for f in feature_of_card_nodes if f.feature.item in new_features_produced_by_needed_combos}
            needed_feature_of_card_nodes.update(new_feature_of_card_nodes)
            new_features_needed_by_needed_combos = {f.item for c in new_needed_combos for features_needed in c.features_needed.values() for f in features_needed}
        self._reset()
        # Return the recipe
        return VariantRecipe(
            cards=ingredients.cards,
            templates=ingredients.templates,
            features=FrozenMultiset(dict(chain(
                ((f.item.feature.id, q) for f, q in countable_feature_nodes.items()),
                ((f.item.feature.id, 1) for f in uncountable_feature_nodes)
            ))),
            combos={cn.item.id for cn in combo_nodes},
            replacements=replacements,
            needed_feature_of_cards={fn.item.id for fn in needed_feature_of_card_nodes},
            needed_combos={cn.item.id for cn in needed_combo_nodes},
        )

    def _check_satisfiability_of_uncountable_features(self, combo: ComboNode, available: set[FeatureWithAttributesNode]) -> bool:
        for feature, group in combo.features_needed.items():
            if feature.uncountable:
                for matcher in group:
                    if matcher.matches.isdisjoint(available):
                        return False
        return True

    def _check_satisfiability_of_countable_features(self, combo: ComboNode, available: dict[FeatureWithAttributesNode, int]) -> bool:
        for feature, group in combo.features_needed.items():
            if not feature.uncountable:
                for matcher, required_quantity in group.items():
                    available_quantity = sum(
                        q
                        for f, q in available.items()
                        if f in matcher.matches
                    )
                    if available_quantity < required_quantity:
                        return False
                required_total_quantity = sum(group.values())
                available_total_quantity = sum(
                    q
                    for f, q in available.items()
                    if f.item.feature == feature and any(f in matcher.matches for matcher in group)
                )
                if available_total_quantity < required_total_quantity:
                    return False
        return True
