from typing import Mapping, Iterable
from collections import deque, defaultdict, Counter
from .multiset import FrozenMultiset, Multiset
from itertools import chain
from enum import Enum
from dataclasses import dataclass
from spellbook.models import Card, Feature, FeatureNeededInCombo, FeatureOfCard, Combo, Template
from .variant_data import AttributesMatcher, Data
from .variant_set import VariantSet, VariantSetParameters, cardid, templateid


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    def __init__(self, graph: 'Graph', item):
        self._variant_set: VariantSet | None = None
        self._filtered_variant_set: VariantSet | None = None
        self._replacement_variant_set: VariantSet | None = None
        self._filtered_replacement_variant_set: VariantSet | None = None
        self.replacements_differ = False
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

    @property
    def replacement_variant_set(self) -> VariantSet | None:
        '''The variant set of this node, restricted to the ingredients taking part in replacements.
        It is what the features produced here are replaced with, both in the texts referencing them and
        in their state and location overrides. Nodes no opted out ingredient can reach share the variant
        set itself, so they cost nothing to keep.'''
        if not self.replacements_differ:
            return self.variant_set
        if self._graph.variant_set_parameters.filter is None:
            return self._replacement_variant_set
        if self._replacement_variant_set is not None and self._filtered_replacement_variant_set is None:
            self._filtered_replacement_variant_set = self._replacement_variant_set.filter(self._graph.variant_set_parameters.filter)
            self._graph._to_reset_nodes_filtered_replacement_variant_set.add(self)
        return self._filtered_replacement_variant_set

    @replacement_variant_set.setter
    def replacement_variant_set(self, value: VariantSet | None):
        if not self.replacements_differ:
            return  # the whole variant set is what the replacements use, so there is nothing of its own to keep
        if self._graph.variant_set_parameters.filter is None:
            self._replacement_variant_set = value
        else:
            self._filtered_replacement_variant_set = value
            self._graph._to_reset_nodes_filtered_replacement_variant_set.add(self)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} of {self.item}'

    def __repr__(self) -> str:
        return self.__str__()

    def _reset_state(self):
        self._state = NodeState.NOT_VISITED

    def _reset_subgraph_state(self):
        self._subgraph_state = NodeState.NOT_VISITED

    def _reset_filtered_variant_set(self):
        self._filtered_variant_set = None

    def _reset_filtered_replacement_variant_set(self):
        self._filtered_replacement_variant_set = None

    def __hash__(self):
        # equality is left as identity on purpose: the graph memoizes one node per item, so two nodes
        # are the same thing only when they are the same object, and lookups resolve without a call
        return self._hash


class NodeWithState(Node):
    def __init__(self, graph: 'Graph', item):
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


class NodeWithoutState(Node):
    def __init__(self, graph: 'Graph', item, variant_set: VariantSet):
        super().__init__(graph, item)
        self._variant_set = variant_set

    @property  # type: ignore[misc]
    def variant_set(self) -> VariantSet:
        return super().variant_set  # type: ignore


class CardNode(NodeWithoutState):
    def __init__(
            self,
            graph: 'Graph',
            card: Card,
            features_of_card: Iterable[FeatureOfCard],
            feature_with_attributes_nodes: dict[int, dict[frozenset[int], 'FeatureWithAttributesNode']],
    ):
        variant_set = VariantSet(
            parameters=graph.variant_set_parameters,
            entries=(VariantSet.ingredients_to_entry(FrozenMultiset({card.id: 1}), FrozenMultiset()),),
        )
        super().__init__(graph, card, variant_set)
        self.combos = dict['ComboNode', int]()
        self.features = list['FeatureOfCardNode']()
        for feature_of_card in features_of_card:
            feature = graph.feature_with_attributes_node(
                feature_with_attributes_nodes,
                feature_of_card.feature_id,
                frozenset(graph.data.feature_of_card_to_attributes[feature_of_card.id]),
            )
            # the same feature can be produced with the same attributes by more than one row
            if any(f.feature is feature for f in self.features):
                continue
            self.features.append(FeatureOfCardNode(graph, feature_of_card, feature_of_card.quantity, self, feature))


class TemplateNode(NodeWithoutState):
    def __init__(self, graph: 'Graph', template: Template):
        variant_set = VariantSet(
            parameters=graph.variant_set_parameters,
            entries=(VariantSet.ingredients_to_entry(FrozenMultiset(), FrozenMultiset({template.id: 1})),),
        )
        super().__init__(graph, template, variant_set)
        self.combos = dict['ComboNode', int]()


class FeatureOfCardNode(NodeWithoutState):
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
        feature.produced_by_cards.append(self)


@dataclass(frozen=True)
class FeatureWithAttributes:
    feature: Feature
    attributes: frozenset[int]


class FeatureWithAttributesNode(NodeWithState):
    def __init__(self, graph: 'Graph', feature: FeatureWithAttributes):
        super().__init__(graph, feature)
        self.produced_by_cards = list[FeatureOfCardNode]()
        self.produced_by_combos = list['ComboNode']()
        self.matches = list['FeatureWithAttributesMatcherNode']()


@dataclass(frozen=True)
class FeatureWithAttributesMatcher:
    feature: Feature
    matcher: AttributesMatcher


class FeatureWithAttributesMatcherNode(NodeWithState):
    def __init__(self, graph: 'Graph', feature: FeatureWithAttributesMatcher):
        super().__init__(graph, feature)
        self.needed_by_combos = dict['ComboNode', int]()
        self.matches = set[FeatureWithAttributesNode]()


def count_needed_features(needed: Iterable[tuple[FeatureNeededInCombo, FeatureWithAttributesMatcherNode]]) -> dict[Feature, Counter[FeatureWithAttributesMatcherNode]]:
    '''How many copies of each feature the given rows ask for, grouped by the matcher asking for them.
    An uncountable feature is only ever needed once, however many rows of the combo ask for it.'''
    result = dict[Feature, Counter[FeatureWithAttributesMatcherNode]]()
    for feature_needed_in_combo, matcher in needed:
        feature = matcher.item.feature
        counter = result.setdefault(feature, Counter())
        counter[matcher] = 1 if feature.uncountable else counter[matcher] + feature_needed_in_combo.quantity
    return result


class ComboNode(NodeWithState):
    '''A combo, holding what it requires both as a whole and as the part of it taking part in the
    replacements. The two are the same collections unless one of its ingredients opted out, so a combo
    where every ingredient participates, which is the norm, keeps a single copy of each.'''

    def __init__(
        self,
        graph: 'Graph',
        combo: Combo,
        feature_with_attributes_nodes: dict[int, dict[frozenset[int], FeatureWithAttributesNode]],
        feature_attributes_matcher_nodes: dict[int, dict[AttributesMatcher, FeatureWithAttributesMatcherNode]],
    ):
        super().__init__(graph, combo)
        data = graph.data
        cards_in_combo = data.combo_to_cards[combo.id]
        templates_in_combo = data.combo_to_templates[combo.id]
        features_needed_in_combo = [
            (
                feature_needed_in_combo,
                graph.feature_with_attributes_matcher_node(
                    feature_attributes_matcher_nodes,
                    feature_needed_in_combo.feature_id,
                    data.feature_needed_in_combo_to_attributes_matcher[feature_needed_in_combo.id],
                ),
            )
            for feature_needed_in_combo in data.combo_to_needed_features[combo.id]
        ]
        self.cards = Multiset[CardNode]({graph.card_nodes[i.card_id]: i.quantity for i in cards_in_combo})
        for card_node, quantity in self.cards.items():
            card_node.combos[self] = quantity
        self.templates = Multiset[TemplateNode]({graph.template_nodes[i.template_id]: i.quantity for i in templates_in_combo})
        for template_node, quantity in self.templates.items():
            template_node.combos[self] = quantity
        self.features_needed = count_needed_features(features_needed_in_combo)
        for features_needed in self.features_needed.values():
            for feature_needed, quantity in features_needed.items():
                feature_needed.needed_by_combos[self] = quantity
        self.features_produced = list[FeatureWithAttributesNode]()
        for feature_produced_in_combo in data.combo_to_produced_features[combo.id]:
            feature_produced = graph.feature_with_attributes_node(
                feature_with_attributes_nodes,
                feature_produced_in_combo.feature_id,
                frozenset(data.feature_produced_in_combo_to_attributes[feature_produced_in_combo.id]),
            )
            # the same feature can be produced with the same attributes by more than one row
            if feature_produced not in self.features_produced:
                self.features_produced.append(feature_produced)
                feature_produced.produced_by_combos.append(self)
        if all(i.in_replacements for i in chain(cards_in_combo, templates_in_combo, data.combo_to_needed_features[combo.id])):
            self.cards_for_replacements = self.cards
            self.templates_for_replacements = self.templates
            self.features_needed_for_replacements = self.features_needed
        else:
            self.cards_for_replacements = Multiset[CardNode]({graph.card_nodes[i.card_id]: i.quantity for i in cards_in_combo if i.in_replacements})
            self.templates_for_replacements = Multiset[TemplateNode]({graph.template_nodes[i.template_id]: i.quantity for i in templates_in_combo if i.in_replacements})
            self.features_needed_for_replacements = count_needed_features((i, matcher) for i, matcher in features_needed_in_combo if i.in_replacements)


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
        found = False
        for p in produced:
            if p.feature == n.feature and n.matcher.matches(p.attributes):
                found = True
                break
        if not found:
            return False
    return True


class GraphError(Exception):
    pass


class Graph:
    def __init__(self,
            data: Data,
            card_limit=5,
            variant_limit=10000,
            allow_multiple_copies=False):
        self.variant_limit = variant_limit
        self.variant_set_parameters = VariantSetParameters(max_depth=card_limit, allow_multiple_copies=allow_multiple_copies)
        self._empty_variant_set = VariantSet(parameters=self.variant_set_parameters)
        self.subgraph = False
        self.data = data
        # shared so that every producer and consumer of a feature gets the same node, and local because they die with the construction
        feature_with_attributes_nodes = dict[featureid, dict[frozenset[int], FeatureWithAttributesNode]]()
        feature_attributes_matcher_nodes = dict[featureid, dict[AttributesMatcher, FeatureWithAttributesMatcherNode]]()
        # nodes register themselves on their related nodes as they are built
        self.card_nodes: dict[cardid, CardNode] = {
            card_id: CardNode(self, card, data.card_to_features[card_id], feature_with_attributes_nodes)
            for card_id, card in data.id_to_card.items()
        }
        self.template_nodes = {template_id: TemplateNode(self, template) for template_id, template in data.id_to_template.items()}
        self.combo_nodes = dict[comboid, ComboNode]()
        for combo_id, combo in data.id_to_combo.items():
            if combo.status not in (Combo.Status.GENERATOR, Combo.Status.UTILITY):
                continue
            if all(i.card_id in self.card_nodes for i in data.combo_to_cards[combo_id]) \
                    and all(i.template_id in self.template_nodes for i in data.combo_to_templates[combo_id]):
                self.combo_nodes[combo_id] = ComboNode(self, combo, feature_with_attributes_nodes, feature_attributes_matcher_nodes)
        for feature_id, d in feature_attributes_matcher_nodes.items():
            candidates = feature_with_attributes_nodes.get(feature_id, {})
            for feature_with_attributes_matcher_node in d.values():
                for attributes, matching_node in candidates.items():
                    if feature_with_attributes_matcher_node.item.matcher.matches(attributes):
                        feature_with_attributes_matcher_node.matches.add(matching_node)
                        matching_node.matches.append(feature_with_attributes_matcher_node)
        self._mark_nodes_with_differing_replacements()
        self._to_reset_nodes_state: set[Node] = set()
        self._to_reset_nodes_subgraph_state: set[Node] = set()
        self._to_reset_nodes_filtered_variant_set: set[Node] = set()
        self._to_reset_nodes_filtered_replacement_variant_set: set[Node] = set()

    def _mark_nodes_with_differing_replacements(self) -> None:
        '''Marks every node whose replacements could differ from its whole variant set: the combos
        with an opted out ingredient, and everything reachable from them by producing a feature another
        combo needs. Marking each node at most once makes this terminate on the cyclic graphs the rest
        of the generation already copes with, and leaves every other node sharing its variant set.'''
        to_visit = deque[Node]()
        for combo_node in self.combo_nodes.values():
            if combo_node.cards_for_replacements is not combo_node.cards \
                    or combo_node.templates_for_replacements is not combo_node.templates \
                    or combo_node.features_needed_for_replacements is not combo_node.features_needed:
                combo_node.replacements_differ = True
                to_visit.append(combo_node)
        while to_visit:
            node = to_visit.popleft()
            if isinstance(node, ComboNode):
                successors: Iterable[Node] = node.features_produced
            elif isinstance(node, FeatureWithAttributesNode):
                successors = node.matches
            else:
                assert isinstance(node, FeatureWithAttributesMatcherNode)
                # the difference only travels through rows that are in replacements
                successors = [
                    combo_node
                    for combo_node in node.needed_by_combos
                    if node in combo_node.features_needed_for_replacements.get(node.item.feature, ())
                ]
            for successor in successors:
                if not successor.replacements_differ:
                    successor.replacements_differ = True
                    to_visit.append(successor)

    def feature_with_attributes_node(self, nodes: dict[featureid, dict[frozenset[int], FeatureWithAttributesNode]], feature_id: int, attributes: frozenset[int]) -> FeatureWithAttributesNode:
        '''The node of a feature produced with the given attributes, shared by every card and combo producing it.
        The index it is memoized in only lives as long as the construction of the graph, so it is passed in.'''
        by_attributes = nodes.setdefault(feature_id, {})
        node = by_attributes.get(attributes)
        if node is None:
            node = FeatureWithAttributesNode(self, FeatureWithAttributes(self.data.id_to_feature[feature_id], attributes))
            by_attributes[attributes] = node
        return node

    def feature_with_attributes_matcher_node(self, nodes: dict[featureid, dict[AttributesMatcher, FeatureWithAttributesMatcherNode]], feature_id: int, matcher: AttributesMatcher) -> FeatureWithAttributesMatcherNode:
        '''The node of a feature needed through the given matcher, shared by every combo needing it that way.'''
        by_matcher = nodes.setdefault(feature_id, {})
        node = by_matcher.get(matcher)
        if node is None:
            node = FeatureWithAttributesMatcherNode(self, FeatureWithAttributesMatcher(self.data.id_to_feature[feature_id], matcher))
            by_matcher[matcher] = node
        return node

    @staticmethod
    def _cached(node: NodeWithState) -> tuple[VariantSet, VariantSet, bool] | None:
        '''The way out of a walk of a node an earlier one already resolved, and None when there is nothing
        to walk out of. The same _resolved call stored its replacement counterpart, so that is there too,
        and both are complete.'''
        variant_set = node.variant_set
        if variant_set is None:
            return None
        replacement_variant_set = node.replacement_variant_set
        assert replacement_variant_set is not None
        node.state = NodeState.VISITED
        return variant_set, replacement_variant_set, True

    @staticmethod
    def _resolved(node: NodeWithState, variant_set: VariantSet, replacement_variant_set: VariantSet, complete: bool) -> tuple[VariantSet, VariantSet, bool]:
        '''The way out of a walk that resolved the node. Only a complete result is stored, so that what is
        cached can never be an under-approximation owed to the cycle the walk happened to be in the middle of.'''
        if complete:
            node.variant_set = variant_set
            node.replacement_variant_set = replacement_variant_set
        node.state = NodeState.VISITED
        return variant_set, replacement_variant_set, complete

    def _unresolved(self) -> tuple[VariantSet, VariantSet, bool]:
        '''The way out of a walk that ran into the cycle the node belongs to. Nothing is cached and the node
        is left visiting on purpose: this emptiness only says the walk was in the middle of that cycle, and
        the node can be resolved for real later on. The empty set is shared, being read only, and rebuilt
        only when the parameters it was built for are replaced.'''
        empty = self._empty_variant_set
        if empty.parameters is not self.variant_set_parameters:
            empty = self._empty_variant_set = VariantSet(parameters=self.variant_set_parameters)
        return empty, empty, False

    def _error(self, msg: str):
        raise Exception(msg)

    def _reset(self):
        node: Node
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
        for node in self._to_reset_nodes_filtered_replacement_variant_set:
            node._reset_filtered_replacement_variant_set()
        self._to_reset_nodes_filtered_replacement_variant_set.clear()
        self.variant_set_parameters = VariantSetParameters(
            max_depth=self.variant_set_parameters.max_depth,
            allow_multiple_copies=self.variant_set_parameters.allow_multiple_copies,
        )

    def variants(self, combo_id: int) -> VariantSet:
        combo_node = self.combo_nodes[combo_id]
        self._reset()
        variant_set, _, _ = self._combo_nodes_down(combo_node)
        return variant_set

    def results(self, variant_set: VariantSet) -> list[VariantRecipe]:
        result = list[VariantRecipe]()
        for cards, templates in variant_set.variants():
            self._reset()
            recipe = self._card_nodes_up(VariantIngredients(cards, templates))
            result.append(recipe)
        return result

    def _combo_nodes_down(self, combo: ComboNode) -> tuple[VariantSet, VariantSet, bool]:
        '''The variant set of a combo, the one restricted to its ingredients in replacements, and
        whether the walk saw everything it depends on. The second is the first itself for the combos no
        opted out ingredient reaches.'''
        if cached := self._cached(combo):
            return cached
        combo.state = NodeState.VISITING
        complete = True
        card_variant_sets: list[VariantSet] = []
        replacement_variant_sets_of_ingredients: list[VariantSet] = []
        for c, q in combo.cards.items():
            variant_set = VariantSet.product_sets([c.variant_set] * q, parameters=self.variant_set_parameters)
            if not variant_set:
                return self._resolved(combo, variant_set, variant_set, complete)
            card_variant_sets.append(variant_set)
            if combo.replacements_differ and c in combo.cards_for_replacements:
                replacement_variant_sets_of_ingredients.append(variant_set)
        template_variant_sets: list[VariantSet] = []
        for t, q in combo.templates.items():
            variant_set = VariantSet.product_sets([t.variant_set] * q, parameters=self.variant_set_parameters)
            if not variant_set:
                return self._resolved(combo, variant_set, variant_set, complete)
            template_variant_sets.append(variant_set)
            if combo.replacements_differ and t in combo.templates_for_replacements:
                replacement_variant_sets_of_ingredients.append(variant_set)
        needed_features_variant_sets: list[VariantSet] = []
        for feature, features_needed in combo.features_needed.items():
            variant_sets = list[VariantSet]()
            replacement_variant_sets = list[VariantSet]()
            # the same matcher can be needed by both participating and opted out rows, so the quantity
            # in replacements is the one counted over the participating rows alone
            features_needed_for_replacements: Mapping[FeatureWithAttributesMatcherNode, int] = combo.features_needed_for_replacements.get(feature, {}) if combo.replacements_differ else {}
            for f, q in features_needed.items():
                if f.state is NodeState.VISITING:
                    return self._unresolved()
                variant_set, replacement_variant_set, complete_below = self._feature_with_attribute_matchers_nodes_down(f)
                complete = complete and complete_below
                variant_sets.extend([variant_set] * q)
                replacement_variant_sets.extend([replacement_variant_set] * features_needed_for_replacements.get(f, 0))
            variant_count_estimate = 0
            for vs in variant_sets:
                variant_count_estimate += len(vs)
            if variant_count_estimate > self.variant_limit:
                raise GraphError(f'{len(variant_sets)} x Feature "{feature}" has too many variants, approx. {variant_count_estimate}')
            variant_set = VariantSet.product_sets(variant_sets, parameters=self.variant_set_parameters)
            if not variant_set:
                return self._resolved(combo, variant_set, variant_set, complete)
            needed_features_variant_sets.append(variant_set)
            if replacement_variant_sets:
                replacement_variant_sets_of_ingredients.append(VariantSet.product_sets(replacement_variant_sets, parameters=self.variant_set_parameters))
        variant_sets = card_variant_sets + template_variant_sets + needed_features_variant_sets
        variant_count_estimate = 1
        for vs in variant_sets:
            variant_count_estimate *= len(vs)
        if variant_count_estimate > self.variant_limit:
            raise GraphError(f'Combo {combo.item} has too many variants, approx. {variant_count_estimate}')
        variant_set = VariantSet.and_sets(variant_sets, parameters=self.variant_set_parameters)
        # no estimate needed: these sets are a subset of the ones already counted
        replacement_variant_set = VariantSet.and_sets(replacement_variant_sets_of_ingredients, parameters=self.variant_set_parameters) if combo.replacements_differ else variant_set
        return self._resolved(combo, variant_set, replacement_variant_set, complete)

    def _feature_with_attribute_matchers_nodes_down(self, feature: FeatureWithAttributesMatcherNode) -> tuple[VariantSet, VariantSet, bool]:
        if cached := self._cached(feature):
            return cached
        feature.state = NodeState.VISITING
        variant_sets: list[VariantSet] = []
        replacement_variant_sets: list[VariantSet] = []
        complete = True
        for m in feature.matches:
            if m.state is NodeState.VISITING:
                complete = False
                continue
            variant_set, replacement_variant_set, complete_below = self._feature_with_attributes_nodes_down(m)
            complete = complete and complete_below
            variant_sets.append(variant_set)
            if feature.replacements_differ:
                replacement_variant_sets.append(replacement_variant_set)
        variant_set = VariantSet.or_sets(variant_sets, parameters=self.variant_set_parameters)
        replacement_variant_set = VariantSet.or_sets(replacement_variant_sets, parameters=self.variant_set_parameters) if feature.replacements_differ else variant_set
        return self._resolved(feature, variant_set, replacement_variant_set, complete)

    def _feature_with_attributes_nodes_down(self, feature: FeatureWithAttributesNode) -> tuple[VariantSet, VariantSet, bool]:
        if cached := self._cached(feature):
            return cached
        feature.state = NodeState.VISITING
        complete = True
        card_variant_sets: list[VariantSet] = [f.variant_set for f in feature.produced_by_cards]
        produced_combos_variant_sets: list[VariantSet] = []
        produced_combos_replacement_variant_sets: list[VariantSet] = []
        for c in feature.produced_by_combos:
            if c.state is NodeState.VISITING:
                complete = False
                continue
            variant_set, replacement_variant_set, complete_below = self._combo_nodes_down(c)
            complete = complete and complete_below
            produced_combos_variant_sets.append(variant_set)
            if feature.replacements_differ:
                produced_combos_replacement_variant_sets.append(replacement_variant_set)
        variant_sets = card_variant_sets + produced_combos_variant_sets
        variant_count_estimate = 0
        for vs in variant_sets:
            variant_count_estimate += len(vs)
        if variant_count_estimate > self.variant_limit:
            raise GraphError(f'Feature "{feature.item}" has too many variants, approx. {variant_count_estimate}')
        variant_set = VariantSet.or_sets(variant_sets, parameters=self.variant_set_parameters)
        replacement_variant_set = VariantSet.or_sets(card_variant_sets + produced_combos_replacement_variant_sets, parameters=self.variant_set_parameters) if feature.replacements_differ else variant_set
        return self._resolved(feature, variant_set, replacement_variant_set, complete)

    def _card_nodes_up(self, ingredients: VariantIngredients) -> VariantRecipe:
        self.variant_set_parameters = VariantSetParameters(
            max_depth=self.variant_set_parameters.max_depth,
            allow_multiple_copies=self.variant_set_parameters.allow_multiple_copies,
            filter=VariantSet.ingredients_to_entry(ingredients.cards, ingredients.templates),
        )
        cards = FrozenMultiset[CardNode]({self.card_nodes[c]: q for c, q in ingredients.cards.items()})
        templates = FrozenMultiset[TemplateNode]({self.template_nodes[t]: q for t, q in ingredients.templates.items()})
        feature_of_card_nodes = set[FeatureOfCardNode]()
        countable_feature_nodes = dict[FeatureWithAttributesNode, int]()
        uncountable_feature_nodes = set[FeatureWithAttributesNode]()
        combo_nodes_to_visit: deque[ComboNode] = deque()
        parked_combo_nodes: set[ComboNode] = set()
        parked_combo_nodes_by_blocking_feature = defaultdict[FeatureWithAttributesNode, list[ComboNode]](list)
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[FeatureWithAttributes, list[VariantIngredients]](list)

        def unpark_combo_nodes_blocked_on(feature: FeatureWithAttributesNode) -> None:
            parked = parked_combo_nodes_by_blocking_feature.pop(feature, None)
            if parked:
                for parked_combo in parked:
                    if parked_combo in parked_combo_nodes:
                        parked_combo_nodes.remove(parked_combo)
                        combo_nodes_to_visit.append(parked_combo)

        for ingredient, quantity in chain(cards.items(), templates.items()):
            for combo in ingredient.combos:  # type: ignore[attr-defined]
                if combo.state is NodeState.NOT_VISITED:
                    if cards.issuperset(combo.cards) and templates.issuperset(combo.templates) or combo.variant_set:
                        combo.state = NodeState.VISITING
                        combo_nodes_to_visit.append(combo)
                    else:
                        combo.state = NodeState.VISITED

        for card, quantity in cards.items():
            for feature_of_card in card.features:
                feature_of_card_nodes.add(feature_of_card)
                feature = feature_of_card.feature
                cards_needed: int = feature_of_card.quantity
                if feature.item.feature.uncountable:
                    feature_count: int = 1
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
                if feature.state is NodeState.VISITED:
                    continue
                feature.state = NodeState.VISITED
                for matching_feature in feature.matches:
                    for feature_combo in matching_feature.needed_by_combos:
                        if feature_combo.state is NodeState.NOT_VISITED:
                            if cards.issuperset(feature_combo.cards) and templates.issuperset(feature_combo.templates) or feature_combo.variant_set:
                                feature_combo.state = NodeState.VISITING
                                combo_nodes_to_visit.append(feature_combo)
                            else:
                                feature_combo.state = NodeState.VISITED

        while combo_nodes_to_visit:
            combo = combo_nodes_to_visit.popleft()
            variant_set: VariantSet | None = None
            replacement_variant_set: VariantSet | None = None
            if combo.variant_set is not None:
                variant_set = combo.variant_set
                if not variant_set:
                    combo.state = NodeState.VISITED
                    continue
                replacement_variant_set = combo.replacement_variant_set
            else:
                blocking_features = self._uncountable_feature_blockers(combo, uncountable_feature_nodes)
                if blocking_features is None:
                    blocking_features = self._countable_feature_blockers(combo, countable_feature_nodes)
                if blocking_features is not None:
                    parked_combo_nodes.add(combo)
                    for blocking_feature in blocking_features:
                        parked_combo_nodes_by_blocking_feature[blocking_feature].append(combo)
                    continue
                if not all(f.item.feature.uncountable for f in combo.features_produced):
                    # the variant set only serves to count how many times the combo fires, so an all-uncountable combo does not need it
                    self.subgraph = True
                    self._reset()
                    variant_set, replacement_variant_set, _ = self._combo_nodes_down(combo)
                    self.subgraph = False
            combo.state = NodeState.VISITED
            combo_nodes.add(combo)
            if variant_set is not None and replacement_variant_set is not None:
                variants_list = variant_set.variants()
                # replacements leave out the opted out ingredients; the firing count does not
                replacements_for_combo: list[VariantIngredients] = [
                    VariantIngredients(cards_replacing, templates_replacing)
                    for cards_replacing, templates_replacing in replacement_variant_set.variants()
                ]
                quantity = 0
                for cards_satisfying, templates_satisfying in variants_list:
                    count_for_cards: int | None = ingredients.cards // cards_satisfying if cards_satisfying else None
                    count_for_templates: int | None = ingredients.templates // templates_satisfying if templates_satisfying else None
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
                        unpark_combo_nodes_blocked_on(feature)
            for feature in combo.features_produced:
                if feature.item.feature.uncountable and feature not in uncountable_feature_nodes:
                    uncountable_feature_nodes.add(feature)
                    unpark_combo_nodes_blocked_on(feature)
                if feature.state is NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    for matching_feature in feature.matches:
                        for feature_combo in matching_feature.needed_by_combos:
                            if feature_combo.state is NodeState.NOT_VISITED:
                                if cards.issuperset(feature_combo.cards) and templates.issuperset(feature_combo.templates) or feature_combo.variant_set:
                                    feature_combo.state = NodeState.VISITING
                                    combo_nodes_to_visit.append(feature_combo)
                                else:
                                    feature_combo.state = NodeState.VISITED

        interesting_features = set[FeatureWithAttributes]()
        for fa_node in chain(countable_feature_nodes.keys(), uncountable_feature_nodes):
            if not fa_node.item.feature.is_utility:
                interesting_features.add(fa_node.item)

        needed_combo_nodes = set[ComboNode]()
        for combo_node in combo_nodes:
            for fa_node in combo_node.features_produced:
                if fa_node.item in interesting_features:
                    needed_combo_nodes.add(combo_node)
                    break

        needed_feature_of_card_nodes = set[FeatureOfCardNode]()
        for foc_node in feature_of_card_nodes:
            if foc_node.feature.item in interesting_features:
                needed_feature_of_card_nodes.add(foc_node)

        new_features_needed_by_needed_combos = set[FeatureWithAttributesMatcher]()
        for combo_node in needed_combo_nodes:
            for features_needed in combo_node.features_needed.values():
                for fam_node in features_needed:
                    new_features_needed_by_needed_combos.add(fam_node.item)

        while not satisfies(interesting_features, new_features_needed_by_needed_combos):
            new_features_produced_by_needed_combos = set[FeatureWithAttributes]()
            for fa in chain(countable_feature_nodes.keys(), uncountable_feature_nodes):
                for fam in new_features_needed_by_needed_combos:
                    if fam.feature == fa.item.feature and fam.matcher.matches(fa.item.attributes):
                        new_features_produced_by_needed_combos.add(fa.item)
                        break

            interesting_features.update(new_features_produced_by_needed_combos)

            new_needed_combos = set[ComboNode]()
            for combo_node in combo_nodes:
                for fa_node in combo_node.features_produced:
                    if fa_node.item in new_features_produced_by_needed_combos:
                        new_needed_combos.add(combo_node)
                        break
            needed_combo_nodes.update(new_needed_combos)

            for foc_node in feature_of_card_nodes:
                if foc_node.feature.item in new_features_produced_by_needed_combos:
                    needed_feature_of_card_nodes.add(foc_node)

            new_features_needed_by_needed_combos.clear()
            for combo_node in new_needed_combos:
                for features_needed in combo_node.features_needed.values():
                    for fam_node in features_needed:
                        new_features_needed_by_needed_combos.add(fam_node.item)
        self._reset()
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

    def _uncountable_feature_blockers(self, combo: ComboNode, available: set[FeatureWithAttributesNode]) -> set[FeatureWithAttributesNode] | None:
        '''Returns the feature nodes whose availability could unblock the combo, or None if it is not blocked.'''
        for feature, group in combo.features_needed.items():
            if feature.uncountable:
                for matcher in group:
                    if matcher.matches.isdisjoint(available):
                        return matcher.matches
        return None

    def _countable_feature_blockers(self, combo: ComboNode, available: dict[FeatureWithAttributesNode, int]) -> set[FeatureWithAttributesNode] | None:
        '''Returns the feature nodes whose quantity increase could unblock the combo, or None if it is not blocked.'''
        for feature, group in combo.features_needed.items():
            if not feature.uncountable:
                for matcher, required_quantity in group.items():
                    matches = matcher.matches
                    available_quantity = 0
                    for f, q in available.items():
                        if f in matches:
                            available_quantity += q
                            if available_quantity >= required_quantity:
                                break
                    if available_quantity < required_quantity:
                        return matches
                required_total_quantity = sum(group.values())
                available_total_quantity = 0
                for f, q in available.items():
                    if f.item.feature == feature:
                        for matcher in group:
                            if f in matcher.matches:
                                available_total_quantity += q
                                break
                        if available_total_quantity >= required_total_quantity:
                            break
                if available_total_quantity < required_total_quantity:
                    blockers = set[FeatureWithAttributesNode]()
                    for matcher in group:
                        blockers.update(matcher.matches)
                    return blockers
        return None
