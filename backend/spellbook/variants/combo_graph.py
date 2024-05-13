from typing import Mapping, Iterable
from math import prod
from collections import deque, defaultdict
from multiset import FrozenMultiset
from typing import Callable, Iterable
from itertools import chain
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
    def __init__(self):
        self.state: NodeState = NodeState.NOT_VISITED
        self.variant_set: VariantSet | None = None

    def __str__(self) -> str:
        return f'{self.__class__} of {self._item()}'

    def __repr__(self) -> str:
        return self.__str__()

    def _item(self):
        return None


class CardNode(Node):
    def __init__(
            self,
            card: Card,
            features: Mapping['FeatureNode', int] = {},
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__()
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
            template: Template,
            combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__()
        self.template = template
        self.combos = dict(combos)

    def __hash__(self):
        return hash(self.template) + 31 * hash('template')

    def _item(self):
        return self.template


class FeatureNode(Node):
    def __init__(
        self,
        feature: Feature,
        produced_by_cards: Mapping[CardNode, int] = {},
        produced_by_combos: Iterable['ComboNode'] = [],
        needed_by_combos: Mapping['ComboNode', int] = {},
    ):
        super().__init__()
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
            combo: Combo,
            cards: Mapping[CardNode, int] = {},
            templates: Mapping[TemplateNode, int] = {},
            features_needed: Mapping[FeatureNode, int] = {},
            features_produced: Iterable[FeatureNode] = [],
    ):
        super().__init__()
        self.combo = combo
        self.cards = dict(cards)
        self.templates = dict(templates)
        self.features_needed = dict(features_needed)
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
        if data is not None:
            self.logger: Callable[[str], None] = log if log is not None else lambda msg: self._error(msg)
            self.data = data
            self.card_limit = card_limit
            self.variant_limit = variant_limit
            # Construct card nodes
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card)) for card in data.cards)
            for c in self.cnodes.values():
                c.variant_set = VariantSet(limit=card_limit)
                c.variant_set.add(FrozenMultiset({c.card.id: 1}), FrozenMultiset())
            # Construct template nodes
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template)) for template in data.templates)
            for t in self.tnodes.values():
                t.variant_set = VariantSet(limit=card_limit)
                t.variant_set.add(FrozenMultiset(), FrozenMultiset({t.template.id: 1}))
            # Construct feature nodes
            self.fnodes = dict[int, FeatureNode]()
            for feature in data.features:
                node = FeatureNode(
                    feature,
                    produced_by_cards={
                        self.cnodes[i.card_id]: i.quantity
                        for i in feature.featureofcard_set.all()  # type: ignore
                        if i.card_id in self.cnodes
                    }
                )
                self.fnodes[feature.id] = node
                for i in feature.featureofcard_set.all():  # type: ignore
                    cardNode = self.cnodes[i.card_id]
                    cardNode.features.update({node: i.quantity})
            # Construct combo nodes
            self.bnodes = dict[int, ComboNode]()
            for combo in data.combos:
                if all(i.card_id in self.cnodes for i in combo.cardincombo_set.all()) and \
                        all(i.template_id in self.tnodes for i in combo.templateincombo_set.all()):
                    node = ComboNode(
                        combo,
                        cards={self.cnodes[i.card_id]: i.quantity for i in combo.cardincombo_set.all()},
                        templates={self.tnodes[i.template_id]: i.quantity for i in combo.templateincombo_set.all()},
                        features_needed={self.fnodes[i.feature_id]: i.quantity for i in combo.featureneededincombo_set.all()},
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
            self.to_reset_nodes = set[Node]()
        else:
            self._error('Invalid arguments')

    def _filter(self, cards: Iterable[int], templates: Iterable[int]) -> 'Graph':
        data = Data(
            cards=[self.cnodes[i].card for i in cards],
            features=[n.feature for n in self.fnodes.values()],
            combos=[n.combo for n in self.bnodes.values()],
            templates=[self.tnodes[i].template for i in templates],
            variants=[],
        )
        return Graph(
            data=data,
            log=self.logger,
            card_limit=self.card_limit,
            variant_limit=self.variant_limit,
        )

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
            result.append(
                self._card_nodes_up(
                    cards={self.cnodes[i]: q for i, q in cards.items()},
                    templates={self.tnodes[i]: q for i, q in templates.items()},
                )
            )
        return result

    def _combo_nodes_down(self, combo: ComboNode) -> VariantSet:
        if combo.variant_set is not None:
            combo.state = NodeState.VISITED
            self.to_reset_nodes.add(combo)
            return combo.variant_set
        combo.state = NodeState.VISITING
        self.to_reset_nodes.add(combo)
        card_variant_sets: list[VariantSet] = [c.variant_set ** q for c, q in combo.cards.items()]  # type: ignore
        template_variant_sets: list[VariantSet] = [t.variant_set ** q for t, q in combo.templates.items()]  # type: ignore
        needed_features_variant_sets: list[VariantSet] = []
        for f, q in combo.features_needed.items():
            if f.state == NodeState.VISITING:
                return VariantSet(limit=self.card_limit)
            variant_set = self._feature_nodes_down(f)
            variants_count_estimate = len(variant_set) * q
            if variants_count_estimate > self.variant_limit:
                msg = f'{q} x Feature "{f.feature}" has too many variants, approx. {variants_count_estimate}'
                self.logger(msg)
                raise Graph.GraphError(msg)
            needed_features_variant_sets.append(variant_set ** q)
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
            self.to_reset_nodes.add(feature)
            return feature.variant_set
        feature.state = NodeState.VISITING
        self.to_reset_nodes.add(feature)
        card_variant_sets: list[VariantSet] = [c.variant_set ** q for c, q in feature.produced_by_cards.items()]  # type: ignore
        produced_combos_variant_sets: list[VariantSet] = []
        for c in feature.produced_by_combos:
            if c.state == NodeState.VISITING:
                continue
            produced_combos_variant_sets.append(self._combo_nodes_down(c))
        variant_sets = card_variant_sets + produced_combos_variant_sets
        variants_count_estimate = sum(len(vs) for vs in variant_sets)
        if variants_count_estimate > self.variant_limit:
            msg = f'Feature "{feature.feature}" has too many variants, approx. {variants_count_estimate}'
            self.logger(msg)
            raise Graph.GraphError(msg)
        feature.variant_set = VariantSet.or_sets(variant_sets, limit=self.card_limit)
        feature.state = NodeState.VISITED
        return feature.variant_set

    def _card_nodes_up(self, cards: Mapping[CardNode, int], templates: Mapping[TemplateNode, int]) -> VariantRecipe:
        for ingredient_node in chain(templates, cards):
            ingredient_node.state = NodeState.VISITED
            self.to_reset_nodes.add(ingredient_node)
        card_ids = FrozenMultiset({c.card.id: q for c, q in cards.items()})
        template_ids = FrozenMultiset({t.template.id: q for t, q in templates.items()})
        sub_graph = self._filter(card_ids.distinct_elements(), template_ids.distinct_elements())
        feature_nodes = defaultdict[FeatureNode, int](lambda: 0)
        combo_nodes_to_visit: deque[ComboNode] = deque()
        combo_nodes: set[ComboNode] = set()
        replacements = defaultdict[int, list[VariantIngredients]](list)
        for card, quantity in cards.items():
            for combo in card.combos:
                if combo.state == NodeState.NOT_VISITED:
                    combo.state = NodeState.VISITING
                    self.to_reset_nodes.add(combo)
                    combo_nodes_to_visit.append(combo)
            for feature, cards_needed in card.features.items():
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    self.to_reset_nodes.add(feature)
                    feature_count = quantity // cards_needed
                    feature_nodes[feature] += feature_count
                    replacements[feature.feature.id].append(
                        VariantIngredients(
                            cards=FrozenMultiset({card.card.id: feature_count * cards_needed}),
                            templates=FrozenMultiset()
                        )
                    )
                    for feature_combo in feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            feature_combo.state = NodeState.VISITING
                            self.to_reset_nodes.add(feature_combo)
                            combo_nodes_to_visit.append(feature_combo)
        while combo_nodes_to_visit:
            combo = combo_nodes_to_visit.popleft()
            variant_set = combo.variant_set if combo.variant_set is not None else sub_graph._combo_nodes_down(combo)
            if variant_set.is_satisfied_by(card_ids, template_ids):
                satisfied_by = variant_set.satisfied_by(card_ids, template_ids)
                replacements_for_combo = [
                    VariantIngredients(cards_satisfying, templates_satisfying)
                    for cards_satisfying, templates_satisfying
                    in satisfied_by
                ]
                for feature in combo.features_produced:
                    replacements[feature.feature.id].extend(replacements_for_combo)
                quantity = 0
                for cards, templates in satisfied_by:
                    count_for_cards = count_contains(card_ids, cards) if cards else None
                    count_for_templates = count_contains(template_ids, templates) if templates else None
                    if count_for_cards is not None:
                        if count_for_templates is not None:
                            quantity += min(count_for_cards, count_for_templates)
                        else:
                            quantity += count_for_cards
                    elif count_for_templates is not None:
                        quantity += count_for_templates
                combo.state = NodeState.VISITED
                combo_nodes.add(combo)
                for feature in combo.features_produced:
                    if feature.state == NodeState.NOT_VISITED:
                        feature.state = NodeState.VISITED
                        self.to_reset_nodes.add(feature)
                        feature_nodes[feature] += quantity
                        for feature_combo in feature.needed_by_combos:
                            if feature_combo.state == NodeState.NOT_VISITED:
                                feature_combo.state = NodeState.VISITING
                                self.to_reset_nodes.add(feature_combo)
                                combo_nodes_to_visit.append(feature_combo)
        return VariantRecipe(
            cards=card_ids,
            templates=template_ids,
            features=FrozenMultiset({f.feature.id: q for f, q in feature_nodes.items()}),
            combos={cn.combo.id for cn in combo_nodes if cn.state == NodeState.VISITED},
            replacements=replacements,
        )
