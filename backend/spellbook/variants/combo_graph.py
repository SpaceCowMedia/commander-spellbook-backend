from typing import Iterable, Optional
from enum import Enum
from ..models import Card, Feature, Combo, Template
from .variant_data import Data
from .variant_trie import VariantTrie, and_tries, or_tries
from dataclasses import dataclass

MAX_CARDS_IN_COMBO = 5


class NodeState(Enum):
    NOT_VISITED = 0
    VISITING = 1
    VISITED = 2


class Node:
    def __init__(self):
        self.state: NodeState = NodeState.NOT_VISITED
        self.trie: Optional[VariantTrie] = None

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
    cards: list[Card]
    templates: list[Template]
    features: list[Feature]
    combos: list[Combo]


class Graph:
    def __init__(self, data: Data):
        if data is not None:
            self.data = data
            self.cnodes = dict[int, CardNode]((card.id, CardNode(card, [], [])) for card in data.cards)
            for c in self.cnodes.values():
                c.trie = VariantTrie(limit=MAX_CARDS_IN_COMBO)
                c.trie.add([c.card.id], [])
            self.tnodes = dict[int, TemplateNode]((template.id, TemplateNode(template, [])) for template in data.templates)
            for t in self.tnodes.values():
                t.trie = VariantTrie(limit=MAX_CARDS_IN_COMBO)
                t.trie.add([], [t.template.id])
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
        else:
            raise Exception('Invalid arguments')

    def reset(self):
        for node in self.cnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.tnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.fnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False
        for node in self.bnodes.values():
            node.state = NodeState.NOT_VISITED
            node.depth = 0
            node.down = False

    def variants(self, combo_id: int) -> Iterable[VariantIngredients]:
        combo = self.bnodes[combo_id]
        # Reset step
        self.reset()
        # Down step
        trie = self._combo_nodes_down(combo)
        # Up step
        for cards, templates in trie.variants():
            self.reset()
            yield self._card_nodes_up([self.cnodes[i] for i in cards], [self.tnodes[i] for i in templates])

    def _combo_nodes_down(self, combo: ComboNode) -> VariantTrie:
        if combo.trie is not None:
            combo.state = NodeState.VISITED
            return combo.trie
        combo.state = NodeState.VISITING
        card_tries = [c.trie for c in combo.cards]
        template_tries = [t.trie for t in combo.templates]
        needed_features_tries: list[VariantTrie] = []
        for f in combo.features_needed:
            if f.state == NodeState.VISITING:
                return VariantTrie()
            needed_features_tries.append(self._feature_nodes_down(f))
        combo.trie = and_tries(card_tries + template_tries + needed_features_tries, limit=MAX_CARDS_IN_COMBO)
        combo.state = NodeState.VISITED
        return combo.trie

    def _feature_nodes_down(self, feature: FeatureNode) -> VariantTrie:
        if feature.trie is not None:
            feature.state = NodeState.VISITED
            return feature.trie
        feature.state = NodeState.VISITING
        card_tries = [c.trie for c in feature.cards]
        produced_combos_tries: list[VariantTrie] = []
        for c in feature.produced_by_combos:
            if c.state == NodeState.VISITING:
                continue
            produced_combos_tries.append(self._combo_nodes_down(c))
        feature.trie = or_tries(card_tries + produced_combos_tries, limit=MAX_CARDS_IN_COMBO)
        feature.state = NodeState.VISITED
        return feature.trie

    def _card_nodes_up(self, cards: list[CardNode], templates: list[TemplateNode]) -> VariantIngredients:
        for featrue_node in templates + cards:
            featrue_node.state = NodeState.VISITED
        card_nodes = set(cards)
        template_nodes = set(templates)
        feature_nodes: set[FeatureNode] = set()
        combo_nodes_to_visit: set[ComboNode] = set()
        combo_nodes: set[ComboNode] = set()
        for card in cards:
            for combo in card.combos:
                if combo.state == NodeState.NOT_VISITED:
                    combo.state = NodeState.VISITING
                    combo_nodes_to_visit.add(combo)
            for feature in card.features:
                if feature.state == NodeState.NOT_VISITED:
                    feature.state = NodeState.VISITED
                    feature_nodes.add(feature)
                    for feature_combo in feature.needed_by_combos:
                        if feature_combo.state == NodeState.NOT_VISITED:
                            feature_combo.state = NodeState.VISITING
                            combo_nodes_to_visit.add(combo)
        flag = True
        while flag:
            flag = False
            for combo in combo_nodes_to_visit:
                if all((c in card_nodes for c in combo.cards)) and all((t in template_nodes for t in combo.templates)) and all((f in feature_nodes for f in combo.features_needed)):
                    combo.state = NodeState.VISITED
                    combo_nodes.add(combo)
                    combo_nodes_to_visit.remove(combo)
                    for feature in combo.features_produced:
                        if feature.state == NodeState.NOT_VISITED:
                            feature.state = NodeState.VISITED
                            feature_nodes.add(feature)
                            for feature_combo in feature.needed_by_combos:
                                if feature_combo.state == NodeState.NOT_VISITED:
                                    feature_combo.state = NodeState.VISITING
                                    combo_nodes_to_visit.add(feature_combo)
                    flag = True
                    break
        return VariantIngredients(
            cards=[cn.card for cn in card_nodes],
            templates=[tn.template for tn in template_nodes],
            features=[fn.feature for fn in feature_nodes],
            combos=[cn.combo for cn in combo_nodes if cn.state == NodeState.VISITED])