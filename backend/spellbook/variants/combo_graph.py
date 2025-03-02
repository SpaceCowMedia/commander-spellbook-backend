from typing import Mapping, Iterable, Generic, TypeVar
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
from .variant_data import AttributesMatcher, Data
from .variant_set import VariantSet, cardid, templateid
from .utils import count_contains


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


T = TypeVar('T')


class Node(Generic[T]):
    def __init__(self, graph: 'Graph', item: T):
        self._state = NodeState.NOT_VISITED
        self._filtered_state = NodeState.NOT_VISITED
        self._variant_set: VariantSet | None = None
        self._filtered_variant_set: VariantSet | None = None
        self._graph = graph
        self.item = item
        self._hash = hash(item) + 31 * hash(self.__class__.__name__)

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
        return f'{self.__class__.__name__} of {self.item}'

    def __repr__(self) -> str:
        return self.__str__()

    def _reset_state(self):
        self._state = NodeState.NOT_VISITED

    def _reset_filtered_state(self):
        self._filtered_state = NodeState.NOT_VISITED

    def _reset_filtered_variant_set(self):
        self._filtered_variant_set = None

    def __hash__(self):
        return self._hash


class CardNode(Node[Card]):
    def __init__(
            self,
            graph: 'Graph',
            card: Card,
            features: Mapping['FeatureWithAttributesNode', int] = {},
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__(graph, card)
        self.features = dict(features)
        self.combos = dict(combos)


class TemplateNode(Node[Template]):
    def __init__(
            self,
            graph: 'Graph',
            template: Template,
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__(graph, template)
        self.combos = dict(combos)


@dataclass(frozen=True)
class FeatureWithAttributes:
    feature: Feature
    attributes: frozenset[int]


class FeatureWithAttributesNode(Node[FeatureWithAttributes]):
    def __init__(
        self,
        graph: 'Graph',
        feature: FeatureWithAttributes,
        produced_by_cards: Mapping[CardNode, int] = {},
        produced_by_combos: Iterable['ComboNode'] = [],
        matches: Iterable['FeatureWithAttributesMatcherNode'] = [],
    ):
        super().__init__(graph, feature)
        self.produced_by_cards = dict(produced_by_cards)
        self.produced_by_combos = list(produced_by_combos)
        self.matches = list(matches)


@dataclass(frozen=True)
class FeatureWithAttributesMatcher:
    feature: Feature
    matcher: AttributesMatcher


class FeatureWithAttributesMatcherNode(Node[FeatureWithAttributesMatcher]):
    def __init__(
        self,
        graph: 'Graph',
        feature: FeatureWithAttributesMatcher,
        needed_by_combos: Mapping['ComboNode', int] = {},
        matches: Iterable[FeatureWithAttributesNode] = [],
    ):
        super().__init__(graph, feature)
        self.needed_by_combos = dict(needed_by_combos)
        self.matches = list(matches)


class ComboNode(Node[Combo]):
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
        self.cards = dict(cards)
        self.templates = dict(templates)
        self.countable_features_needed = dict(countable_features_needed)
        self.uncountable_features_needed = list(uncountable_features_needed)
        self.features_produced = list(features_produced)

    @property
    def features_needed(self) -> Iterable[FeatureWithAttributesMatcherNode]:
        return chain(self.countable_features_needed.keys(), self.uncountable_features_needed)


@dataclass(frozen=True)
class VariantIngredients:
    cards: FrozenMultiset[cardid]
    templates: FrozenMultiset[templateid]


featureid = int
comboid = int


@dataclass(frozen=True)
class VariantRecipe(VariantIngredients):
    features: FrozenMultiset[featureid]
    combos: set[comboid]
    replacements: dict[FeatureWithAttributes, list[VariantIngredients]]
    needed_features: set[featureid]
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
        self.card_limit = card_limit
        self.variant_limit = variant_limit
        self.allow_multiple_copies = allow_multiple_copies
        self.filter: VariantIngredients | None = None
        self.data = data
        # Construct card nodes
        self.cnodes = {card_id: CardNode(self, card) for card_id, card in data.id_to_card.items()}
        # Construct feature with attributes nodes
        self.fanodes = dict[featureid, dict[frozenset[int], FeatureWithAttributesNode]]()
        # Iterate over cards
        for card_id, c in self.cnodes.items():
            c.variant_set = self._new_variant_set()
            c.variant_set.add(FrozenMultiset({card_id: 1}), FrozenMultiset())
            for feature_produced_by_card in data.card_to_features[card_id]:
                attributes = frozenset(data.feature_of_card_to_attributes[feature_produced_by_card.id])
                fa = self.fanodes.setdefault(feature_produced_by_card.feature_id, {}).setdefault(
                    attributes,
                    FeatureWithAttributesNode(
                        self,
                        FeatureWithAttributes(
                            data.id_to_feature[feature_produced_by_card.feature_id],
                            attributes,
                        ),
                    )
                )
                fa.produced_by_cards[c] = feature_produced_by_card.quantity
                c.features[fa] = feature_produced_by_card.quantity
        # Construct template nodes
        self.tnodes = {template_id: TemplateNode(self, template) for template_id, template in data.id_to_template.items()}
        for t in self.tnodes.values():
            t.variant_set = self._new_variant_set()
            t.variant_set.add(FrozenMultiset(), FrozenMultiset({t.item.id: 1}))
        # Construct feature with attribute matchers nodes
        self.famnodes = dict[featureid, dict[AttributesMatcher, FeatureWithAttributesMatcherNode]]()
        # Construct combo nodes
        self.bnodes = dict[comboid, ComboNode]()
        for combo_id, combo in data.id_to_combo.items():
            if combo.status not in (Combo.Status.GENERATOR, Combo.Status.UTILITY):
                continue
            if all(i.card_id in self.cnodes for i in data.combo_to_cards[combo_id]) \
                    and all(i.template_id in self.tnodes for i in data.combo_to_templates[combo_id]):
                b = ComboNode(self, combo)
                self.bnodes[combo_id] = b
                for card_in_combo in data.combo_to_cards[combo_id]:
                    c = self.cnodes[card_in_combo.card_id]
                    c.combos[b] = card_in_combo.quantity
                    b.cards[c] = card_in_combo.quantity
                for template_in_combo in data.combo_to_templates[combo_id]:
                    t = self.tnodes[template_in_combo.template_id]
                    t.combos[b] = template_in_combo.quantity
                    b.templates[t] = template_in_combo.quantity
                for feature_produced_by_combo in data.combo_to_produced_features[combo_id]:
                    attributes = frozenset(data.feature_produced_in_combo_to_attributes[feature_produced_by_combo.id])
                    fa = self.fanodes.setdefault(feature_produced_by_combo.feature_id, {}).setdefault(
                        attributes,
                        FeatureWithAttributesNode(
                            self,
                            FeatureWithAttributes(
                                data.id_to_feature[feature_produced_by_combo.feature_id],
                                attributes,
                            ),
                        )
                    )
                    fa.produced_by_combos.append(b)
                    b.features_produced.append(fa)
                for feature_needed_by_combo in data.combo_to_needed_features[combo.id]:
                    attributes_matcher = data.feature_needed_in_combo_to_attributes_matcher[feature_needed_by_combo.id]
                    fam = self.famnodes.setdefault(feature_needed_by_combo.feature_id, {}).setdefault(
                        attributes_matcher,
                        FeatureWithAttributesMatcherNode(
                            self,
                            FeatureWithAttributesMatcher(
                                data.id_to_feature[feature_needed_by_combo.feature_id],
                                attributes_matcher,
                            ),
                        )
                    )
                    if fam.item.feature.uncountable:
                        fam.needed_by_combos[b] = 1
                        b.uncountable_features_needed.append(fam)
                    else:
                        fam.needed_by_combos[b] = fam.needed_by_combos.get(b, 0) + feature_needed_by_combo.quantity
                        b.countable_features_needed[fam] = b.countable_features_needed.get(fam, 0) + feature_needed_by_combo.quantity
        # Find matching feature with attributes nodes
        for feature_id, d in self.famnodes.items():
            candidates = self.fanodes.get(feature_id, {})
            for fam in d.values():
                for attributes, matching_node in candidates.items():
                    if fam.item.matcher.matches(attributes):
                        fam.matches.append(matching_node)
                        matching_node.matches.append(fam)
        self._to_reset_nodes_state = set[Node]()
        self._to_reset_nodes_filtered_state = set[Node]()
        self._to_reset_nodes_filtered_variant_set = set[Node]()

    def _new_variant_set(self) -> VariantSet:
        return VariantSet(limit=self.card_limit, allow_multiple_copies=self.allow_multiple_copies)

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
                combo.variant_set = self._new_variant_set()
                return combo.variant_set
            card_variant_sets.append(variant_set)
        template_variant_sets: list[VariantSet] = []
        for t, q in combo.templates.items():
            variant_set: VariantSet = t.variant_set ** q  # type: ignore
            if self.filter is not None:
                variant_set = variant_set.filter(self.filter.cards, self.filter.templates)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = self._new_variant_set()
                return combo.variant_set
            template_variant_sets.append(variant_set)
        needed_features_variant_sets: list[VariantSet] = []
        for f, q in chain(combo.countable_features_needed.items(), zip(combo.uncountable_features_needed, repeat(1))):
            if f.state == NodeState.VISITING:
                return self._new_variant_set()
            variant_set = self._feature_with_attribute_matchers_nodes_down(f)
            variant_count_estimate = len(variant_set) * q
            if variant_count_estimate > self.variant_limit:
                raise Graph.GraphError(f'{q} x Feature "{f.item}" has too many variants, approx. {variant_count_estimate}')
            variant_set = variant_set ** q
            if self.filter is not None:
                variant_set = variant_set.filter(self.filter.cards, self.filter.templates)
            if not variant_set:
                combo.state = NodeState.VISITED
                combo.variant_set = self._new_variant_set()
                return combo.variant_set
            needed_features_variant_sets.append(variant_set)
        variant_sets: list[VariantSet] = card_variant_sets + template_variant_sets + needed_features_variant_sets
        variant_count_estimate = prod(len(vs) for vs in variant_sets)
        if variant_count_estimate > self.variant_limit:
            raise Graph.GraphError(f'Combo {combo.item} has too many variants, approx. {variant_count_estimate}')
        combo.variant_set = VariantSet.and_sets(variant_sets, limit=self.card_limit, allow_multiple_copies=self.allow_multiple_copies)
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
        feature.variant_set = VariantSet.or_sets(variant_sets, limit=self.card_limit, allow_multiple_copies=self.allow_multiple_copies)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _feature_with_attributes_nodes_down(self, feature: FeatureWithAttributesNode) -> VariantSet:
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
        variant_count_estimate = sum(len(vs) for vs in variant_sets)
        if variant_count_estimate > self.variant_limit:
            raise Graph.GraphError(f'Feature "{feature.item}" has too many variants, approx. {variant_count_estimate}')
        feature.variant_set = VariantSet.or_sets(variant_sets, limit=self.card_limit, allow_multiple_copies=self.allow_multiple_copies)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _card_nodes_up(self, ingredients: VariantIngredients) -> VariantRecipe:
        cards = {self.cnodes[c]: q for c, q in ingredients.cards.items()}
        templates = {self.tnodes[t]: q for t, q in ingredients.templates.items()}
        for ingredient_node in chain(templates, cards):
            ingredient_node.state = NodeState.VISITED
        countable_feature_nodes = dict[FeatureWithAttributesNode, int]()
        uncountable_feature_nodes = set[FeatureWithAttributesNode]()
        combo_nodes_to_visit: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_countable_features: deque[ComboNode] = deque()
        combo_nodes_to_visit_with_new_uncountable_features: deque[ComboNode] = deque()
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[FeatureWithAttributes, list[VariantIngredients]](list)
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
                if feature.item.feature.uncountable:
                    uncountable_feature_nodes.add(feature)
                    feature_count = 1
                else:
                    feature_count = quantity // cards_needed
                    countable_feature_nodes[feature] = countable_feature_nodes.get(feature, 0) + feature_count
                replacements[feature.item].append(
                    VariantIngredients(
                        cards=FrozenMultiset({card.item.id: cards_needed}),
                        templates=FrozenMultiset()
                    )
                )
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    for matching_feature in feature.matches:
                        for feature_combo in matching_feature.needed_by_combos:
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
                if any(all(q > countable_feature_nodes.get(ff, 0) for ff in f.matches) for f, q in combo.countable_features_needed.items()):
                    combo_nodes_to_visit_with_new_countable_features.append(combo)
                    continue
                if any(all(ff not in uncountable_feature_nodes for ff in f.matches) for f in combo.uncountable_features_needed):
                    combo_nodes_to_visit_with_new_uncountable_features.append(combo)
                    continue
                if not all(f.item.feature.uncountable for f in combo.features_produced):
                    # it makes sense to compute the variant set only if the combo produces countable features
                    # variant set is only used to determine the amount of times the combo is used
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
                                if all(c in cards and cards[c] >= q for c, q in feature_combo.cards.items()) \
                                        and all(t in templates and templates[t] >= q for t, q in feature_combo.templates.items()):
                                    feature_combo.state = NodeState.VISITING
                                    combo_nodes_to_visit.append(feature_combo)
                                else:
                                    feature_combo.state = NodeState.VISITED
        # Compute needed features and combos
        interesting_features = set[FeatureWithAttributes](  # by default interesting features are not utility features
            f.item
            for f in chain(countable_feature_nodes.keys(), uncountable_feature_nodes)
            if not f.item.feature.status == Feature.Status.UTILITY
        )
        needed_combo_nodes = set[ComboNode](  # by default needed combos produce interesting features
            c
            for c in combo_nodes
            if any(f.item in interesting_features for f in c.features_produced)
        )
        new_features_needed_by_needed_combos = {f.item for c in needed_combo_nodes for f in c.features_needed}
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
            new_features_needed_by_needed_combos = {f.item for c in new_needed_combos for f in c.features_needed}
        # Return the recipe
        return VariantRecipe(
            cards=ingredients.cards,
            templates=ingredients.templates,
            features=FrozenMultiset({
                f.item.feature.id: q for f, q in countable_feature_nodes.items()
            } | {
                f.item.feature.id: 1 for f in uncountable_feature_nodes
            }),
            combos={cn.item.id for cn in combo_nodes if cn.state == NodeState.VISITED},
            replacements=replacements,
            needed_features={f.feature.id for f in interesting_features},
            needed_combos={cn.item.id for cn in needed_combo_nodes},
        )
