import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
from itertools import chain, count
from typing import Callable, Collection, Generic, Iterable, Iterator, Mapping, Sequence, TypeVar
from django.db.models import Model
from .variant_data import Data
from .variant_set import cardid, templateid
from .combo_graph import FeatureWithAttributes, comboid, featureid
from spellbook.models import Card, CardInVariant, CardType, Combo, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, Ingredient, Template, TemplateInVariant, ZoneLocation, join_with_conjunction, merge_mana_costs
from spellbook.models.references import CARD_STATE_KEYS, DEFAULT_KEY, FEATURE_REFERENCE_PATTERN, LINE_REFERENCE_PATTERN, TEXT_KEYS, expand_aliases, key_of, referenced_line


FeatureName = str
Key = str
# Position of a source among the ones a variant takes its texts from
SourceIndex = int
# How the several texts of one field are combined into the single text of the variant
MergeTexts = Callable[[Iterable[str]], str]
Recipe = tuple[list[Card], list[Template]]
# What a dictionary stored on a row maps a key to
StoredValue = str | list[str]

_V = TypeVar('_V')

# How deep a dictionary text referencing other dictionaries is followed, so that a cycle of them ends
MAX_REFERENCE_DEPTH = 8


# ---------------------------------------------------------------------------
# The sources a variant takes its texts from
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Override:
    '''A text a dictionary writes for one field of a variant in place of what its row brings, kept as a
    source of its own placed right after the source owning the dictionary, so that it is written,
    included and ordered like any other text. It resolves its references against the combo owning it.
    Its mana is an accurate minimum unless the card feature owning it says otherwise.'''
    owner: SourceIndex
    combo_id: comboid | None
    field: str
    text: str
    is_mana_needed_an_accurate_minimum: bool = True


# A text of a variant is written by a combo it needs, by a feature of one of its cards, or by a dictionary
TextSource = Combo | FeatureOfCard | Override


def text_of(source: TextSource, field: str) -> str:
    if isinstance(source, Override):
        return source.text if source.field == field else ''
    return getattr(source, field, '')


def owning_combo_id(source: TextSource) -> comboid | None:
    '''The combo a source resolves its feature names against: a text written on a card has none.'''
    if isinstance(source, Override):
        return source.combo_id
    return source.id if isinstance(source, Combo) else None


def stored_texts(value: StoredValue) -> list[str]:
    '''The texts a stored value holds, blanks left out.'''
    return [text for text in ([value] if isinstance(value, str) else value) if text]


def combo_rows(data: Data, combo: Combo) -> Iterable[Model]:
    '''Every row of a combo holding a dictionary.'''
    return chain(data.combo_to_cards[combo.id], data.combo_to_templates[combo.id], data.combo_to_needed_features[combo.id], data.combo_to_produced_features[combo.id])


def collect_sources(data: Data, feature_of_cards: Sequence[FeatureOfCard], combos: Sequence[Combo]) -> tuple[list[TextSource], dict[tuple[Model, Key], list[SourceIndex]]]:
    '''The sources of a variant in the order their texts are written: the features of its cards, then
    its combos, each followed by the texts the dictionaries of its rows write, and where those are, by
    row and key.'''
    sources = list[TextSource]()
    overrides = dict[tuple[Model, Key], list[SourceIndex]]()

    def add_overrides(owner: SourceIndex, combo_id: comboid | None, row: Model, accurate: bool = True) -> None:
        for key, value in row.dictionary.items():  # type: ignore[attr-defined]
            if key in TEXT_KEYS:
                indices = overrides.setdefault((row, key), [])
                for text in stored_texts(value):
                    indices.append(len(sources))
                    sources.append(Override(owner, combo_id, key, text, accurate or key != 'mana_needed'))

    for feature_of_card in feature_of_cards:
        owner = len(sources)
        sources.append(feature_of_card)
        add_overrides(owner, None, feature_of_card, feature_of_card.is_mana_needed_an_accurate_minimum)
    for combo in combos:
        owner = len(sources)
        sources.append(combo)
        for row in combo_rows(data, combo):
            add_overrides(owner, combo.id, row)
    return sources, overrides


def produced_features(data: Data, source: TextSource) -> Iterable[tuple[featureid, frozenset[int]]]:
    '''The features a source produces, with the attributes it produces them with.'''
    if isinstance(source, Combo):
        return [
            (row.feature_id, frozenset(data.feature_produced_in_combo_to_attributes[row.id]))
            for row in data.combo_to_produced_features[source.id]
        ]
    if isinstance(source, FeatureOfCard):
        return [(source.feature_id, frozenset(data.feature_of_card_to_attributes[source.id]))]
    return []


Root = tuple[SourceIndex, FeatureWithAttributes | None]


def roots_of(data: Data, sources: Sequence[TextSource], generator_combo_ids: Collection[comboid]) -> list[Root]:
    '''The sources a variant holds for their own sake, the way the combo graph starts collecting the
    needed ones: its generator combos, and every source producing a feature that is no utility, or
    removing one the variant produces. Everything else is there to satisfy one of their rows. A combo
    producing such features is held as the producer of each of them, for the dictionary of the row
    producing it to override what it writes there.'''
    results = {
        feature_id
        for source in sources
        for feature_id, _ in produced_features(data, source)
        if feature_id not in data.utility_features_ids
    }
    roots = list[Root]()
    for index, source in enumerate(sources):
        produced = [(feature_id, attributes) for feature_id, attributes in produced_features(data, source) if feature_id in results]
        if produced and isinstance(source, Combo):
            roots.extend((index, FeatureWithAttributes(data.id_to_feature[feature_id], attributes)) for feature_id, attributes in produced)
        elif produced or isinstance(source, Combo) and (source.id in generator_combo_ids or any(row.feature_id in results for row in data.combo_to_removed_features[source.id])):
            roots.append((index, None))
    return roots


# ---------------------------------------------------------------------------
# What a feature provides: dictionaries of keys
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Item:
    '''One of the things a key holds, ordered among the others by where it is written: an ingredient
    named in the display order of the variant, a text of a source in source order, or a text a
    dictionary holds, which resolves its references against the combo owning it.'''
    order: tuple[int, int, int]
    source: SourceIndex | None = None
    text: str = ''
    combo_id: comboid | None = None
    card: Card | None = None
    template: Template | None = None


@dataclass(frozen=True)
class Value:
    '''What a key holds: a text, which any override replaces, or a list, which a list override extends.'''
    items: tuple[Item, ...] = ()
    listed: bool = False


EMPTY_VALUE = Value()
Dictionary = dict[Key, Value]


def override(base: Mapping[Key, Value], stored: Mapping[Key, StoredValue], item_of: Callable[[Key, int, str], Item]) -> Dictionary:
    '''What a row brings once its dictionary overrides it: a text replaces whatever the key held, a
    blank one leaving it out, and a list extends a list or replaces a text.'''
    result = dict(base)
    for key, value in stored.items():
        items = tuple(item_of(key, position, text) for position, text in enumerate(stored_texts(value)))
        previous = result.get(key)
        if isinstance(value, str):
            result[key] = Value(items)
        elif previous is not None and previous.listed:
            result[key] = Value(previous.items + items, listed=True)
        else:
            result[key] = Value(items, listed=True)
    return result


def combine(dictionaries: Iterable[Mapping[Key, Value]]) -> Dictionary:
    '''What siblings bring together, whatever their order: a text counts as a list of one, a blank brings
    nothing, and the lists are joined in the order their items are written. A key only one of them fills
    keeps its value as it is.'''
    gathered = defaultdict[Key, list[Value]](list)
    for dictionary in dictionaries:
        for key, value in dictionary.items():
            gathered[key].append(value)
    result = Dictionary()
    for key, values in gathered.items():
        filled = [value for value in values if value.items]
        if not filled:
            result[key] = EMPTY_VALUE
        elif len(filled) == 1:
            result[key] = filled[0]
        else:
            items = dict.fromkeys(item for value in filled for item in value.items)
            result[key] = Value(tuple(sorted(items, key=lambda item: item.order)), listed=True)
    return result


def sources_of(value: Value) -> list[SourceIndex]:
    return [item.source for item in value.items if item.source is not None]


@dataclass(eq=False)
class Way:
    '''One way of producing a feature in a variant: the ingredients the graph found for it, then what
    they provide and every source producing something on the way, once the context walked it.'''
    feature: FeatureWithAttributes
    cards: tuple[Card, ...]
    templates: tuple[Template, ...]
    dictionary: Dictionary = field(default_factory=dict)
    sources: frozenset[SourceIndex] = frozenset()

    def named(self) -> tuple[Item, ...]:
        '''The ingredients this way names, which the starting location override of a row it satisfies reaches.'''
        return self.dictionary.get(DEFAULT_KEY, EMPTY_VALUE).items


class DictionaryBuilder:
    '''Builds what each source of a variant provides out of its own texts, the names of its ingredients
    and what its needed rows reach, each overridden by the dictionary of its row.'''

    def __init__(self, data: Data, sources: Sequence[TextSource], overrides: Mapping[tuple[Model, Key], Sequence[SourceIndex]], positions: 'IngredientPositions') -> None:
        self.data = data
        self.sources = sources
        self.overrides = overrides
        self.positions = positions
        self.producers = defaultdict[featureid, list[tuple[SourceIndex, frozenset[int]]]](list)
        for index, source in enumerate(sources):
            for feature_id, attributes in produced_features(data, source):
                self.producers[feature_id].append((index, attributes))

    def item_of(self, row: Model, owner: SourceIndex, combo_id: comboid | None) -> Callable[[Key, int, str], Item]:
        '''How the texts of the dictionary of a row become items: a text of a variant is the source it
        was collected as, any other text is written as it is.'''
        def item(key: Key, position: int, text: str) -> Item:
            if key in TEXT_KEYS:
                index = self.overrides[row, key][position]
                return Item(order=(1, index, 0), source=index)
            return Item(order=(1, owner, position), text=text, combo_id=combo_id)
        return item

    def own(self, index: SourceIndex) -> Dictionary:
        '''The texts a source writes itself, under the keys of their fields. Like names, they are lists,
        which a list in a dictionary extends.'''
        source = self.sources[index]
        return {key: Value((Item(order=(1, index, 0), source=index),), listed=True) for key in TEXT_KEYS if text_of(source, key)}

    def card(self, card: Card) -> Dictionary:
        return {DEFAULT_KEY: Value((Item(order=(0, self.positions.of_card(card_number(card)), 0), card=card),), listed=True)}

    def template(self, template: Template) -> Dictionary:
        return {DEFAULT_KEY: Value((Item(order=(0, self.positions.of_template(template.id), 0), template=template),), listed=True)}

    def feature_of_card(self, index: SourceIndex) -> Dictionary:
        '''What a card provides for a feature it produces: its name and its dictionary, whose texts and
        names are lists, like the ones a combo brings, for a list overriding them to extend them.'''
        source = self.sources[index]
        assert isinstance(source, FeatureOfCard)
        provided = override(self.card(self.data.id_to_card[source.card_id]), source.dictionary, self.item_of(source, index, None))
        return {key: Value(value.items, listed=True) if key == DEFAULT_KEY or key in TEXT_KEYS else value for key, value in provided.items()}

    def combo(self, index: SourceIndex, reached: Callable[[FeatureNeededInCombo], Dictionary]) -> Dictionary:
        '''What a combo brings: its own texts, the names of its cards and templates, and what each of its
        needed rows reaches, each overridden by the dictionary of its row.'''
        combo = self.sources[index]
        assert isinstance(combo, Combo)
        parts = [self.own(index)]
        for card_in_combo in self.data.combo_to_cards[combo.id]:
            parts.append(override(self.card(self.data.id_to_card[card_in_combo.card_id]), card_in_combo.dictionary, self.item_of(card_in_combo, index, combo.id)))
        for template_in_combo in self.data.combo_to_templates[combo.id]:
            parts.append(override(self.template(self.data.id_to_template[template_in_combo.template_id]), template_in_combo.dictionary, self.item_of(template_in_combo, index, combo.id)))
        for row in self.data.combo_to_needed_features[combo.id]:
            parts.append(override(reached(row), row.dictionary, self.item_of(row, index, combo.id)))
        return combine(parts)

    def produced_row(self, index: SourceIndex, feature: FeatureWithAttributes) -> FeatureProducedInCombo | None:
        '''The row a combo produces a feature with, whose dictionary overrides what the combo provides for it.'''
        combo = self.sources[index]
        assert isinstance(combo, Combo)
        for row in self.data.combo_to_produced_features[combo.id]:
            if row.feature_id == feature.feature.id and frozenset(self.data.feature_produced_in_combo_to_attributes[row.id]) == feature.attributes:
                return row
        return None

    def produced(self, index: SourceIndex, feature: FeatureWithAttributes, dictionary: Dictionary) -> Dictionary:
        '''What a combo provides for one feature it produces: what it brings, overridden by the
        dictionary of the row producing that feature.'''
        row = self.produced_row(index, feature)
        return override(dictionary, row.dictionary, self.item_of(row, index, row.combo_id)) if row is not None else dictionary

    def fits(self, index: SourceIndex, cards: frozenset[cardid], templates: frozenset[templateid]) -> bool:
        '''Whether every ingredient of a source is in a way.'''
        source = self.sources[index]
        if isinstance(source, FeatureOfCard):
            return source.card_id in cards
        assert isinstance(source, Combo)
        return all(row.card_id in cards for row in self.data.combo_to_cards[source.id]) \
            and all(row.template_id in templates for row in self.data.combo_to_templates[source.id])

    def producers_of(self, row: FeatureNeededInCombo, among: Collection[SourceIndex] | None = None) -> list[tuple[SourceIndex, FeatureWithAttributes]]:
        '''The sources producing the feature a row needs with attributes it accepts, among the given ones
        if any, along with the feature as they produce it.'''
        matcher = self.data.feature_needed_in_combo_to_attributes_matcher[row.id]
        return [
            (producer, FeatureWithAttributes(self.data.id_to_feature[row.feature_id], attributes))
            for producer, attributes in self.producers[row.feature_id]
            if (among is None or producer in among) and matcher.matches(attributes)
        ]

    def as_producer(self, index: SourceIndex, feature: FeatureWithAttributes, dictionary: Dictionary) -> Dictionary:
        '''What a source brings as the producer of a feature: a combo overrides it with the dictionary of
        the row producing that feature.'''
        return self.produced(index, feature, dictionary) if isinstance(self.sources[index], Combo) else dictionary

    def satisfiable(self, cards: frozenset[cardid], templates: frozenset[templateid]) -> set[SourceIndex]:
        '''The sources that can produce inside a way: the ones whose ingredients are all in it, and whose
        every needed row is satisfied by another one of them, found as a fixpoint so that a cycle of
        combos needing each other's features costs nothing more than any other.'''
        fitting = [index for index, source in enumerate(self.sources) if not isinstance(source, Override) and self.fits(index, cards, templates)]
        satisfiable = set[SourceIndex]()
        changed = True
        while changed:
            changed = False
            for index in fitting:
                if index in satisfiable:
                    continue
                source = self.sources[index]
                if isinstance(source, FeatureOfCard) or isinstance(source, Combo) and all(self.producers_of(row, satisfiable) for row in self.data.combo_to_needed_features[source.id]):
                    satisfiable.add(index)
                    changed = True
        return satisfiable

    def walk(self, way: Way) -> None:
        '''Fills in what a way provides, out of every source producing its feature inside it, each one
        bringing what its rows reach inside it in turn. Each source is walked once: one met again while
        it is being walked, in a cycle, adds nothing there, since it already brings its own. A way no
        source can be found for, which the graph never yields, names its ingredients.'''
        satisfiable = self.satisfiable(frozenset(card_number(card) for card in way.cards), frozenset(template.id for template in way.templates))
        walked = dict[SourceIndex, Dictionary]()
        walking = set[SourceIndex]()

        def brought(index: SourceIndex) -> Dictionary | None:
            if index in walked:
                return walked[index]
            if index in walking:
                return None
            source = self.sources[index]
            if isinstance(source, FeatureOfCard):
                walked[index] = self.feature_of_card(index)
                return walked[index]
            assert isinstance(source, Combo)
            walking.add(index)
            reached = {
                row.id: combine(
                    self.as_producer(producer, feature, dictionary)
                    for producer, feature in self.producers_of(row, satisfiable)
                    if (dictionary := brought(producer)) is not None
                )
                for row in self.data.combo_to_needed_features[source.id]
            }
            walking.discard(index)
            walked[index] = self.combo(index, lambda row: reached[row.id])
            return walked[index]

        dictionaries = list[Dictionary]()
        for index, attributes in self.producers[way.feature.feature.id]:
            if attributes == way.feature.attributes and index in satisfiable:
                dictionary = brought(index)
                assert dictionary is not None
                dictionaries.append(self.as_producer(index, way.feature, dictionary))
        if not dictionaries:
            dictionaries = [*map(self.card, way.cards), *map(self.template, way.templates)]
        way.dictionary = combine(dictionaries)
        way.sources = frozenset(walked)

    def written_by_default(self, roots: Iterable[Root], key: Key) -> frozenset[SourceIndex]:
        '''The sources a variant writes one of its fields with on its own: the ones it holds for their own
        sake, and every one their needed rows reach in turn, each row reaching every source producing what
        it accepts, the way the variant itself was found. A dictionary overriding the key on the way writes
        its texts instead, a text cutting off what that row brings, and a list adding to it. The row a
        combo produces a feature with does the same wherever the combo writes as its producer, the
        variant's own results included.'''
        written = set[SourceIndex]()

        def overridden(row: Model) -> bool:
            value = row.dictionary.get(key)  # type: ignore[attr-defined]
            if value is None:
                return False
            written.update(self.overrides.get((row, key), ()))
            return isinstance(value, str)

        visited = set[Root]()
        to_visit = list(roots)
        while to_visit:
            index, feature = to_visit.pop()
            if (index, feature) in visited:
                continue
            visited.add((index, feature))
            source = self.sources[index]
            if isinstance(source, FeatureOfCard):
                overridden(source)
                continue
            assert isinstance(source, Combo)
            if feature is not None and (row := self.produced_row(index, feature)) is not None and overridden(row):
                continue
            if text_of(source, key):
                written.add(index)
            for ingredient in chain(self.data.combo_to_cards[source.id], self.data.combo_to_templates[source.id]):
                overridden(ingredient)
            for needed in self.data.combo_to_needed_features[source.id]:
                if not overridden(needed):
                    to_visit.extend(self.producers_of(needed))
        return frozenset(written)


# ---------------------------------------------------------------------------
# What a feature name resolves to
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Alternative:
    '''One way a feature name resolves in a variant, and the attributes the feature was produced with.
    Alternatives are what a selector picks between and what the needed feature rows of a combo are dealt.'''
    way: Way
    attribute_ids: frozenset[int] = frozenset()
    # sorted, in their original case: they order the alternatives of a feature and answer a selector
    attribute_names: tuple[str, ...] = ()

    def has_attribute(self, name: str) -> bool:
        return any(attribute.casefold() == name.casefold() for attribute in self.attribute_names)


@dataclass(frozen=True)
class Offer:
    '''The alternatives a combo sees for a feature it needs, the ones dealt to its rows first.'''
    alternatives: tuple[Alternative, ...] = ()
    dealt: int = 0


def select(offer: Offer, selector: str | None, surplus: bool = False) -> list[Way]:
    '''What a selector picks among the alternatives of a feature: an attribute name keeps the ones the
    feature was produced with it, a number picks the one at that position, and no selector keeps the
    ones dealt to the rows of the combo, or all of them when none was. With the surplus, no selector
    also keeps the ones dealt to no row, which every row accepting them reaches. Nothing selected means
    the reference has nothing to write.'''
    if selector is None:
        return [alternative.way for alternative in (offer.alternatives if surplus else offer.alternatives[:offer.dealt or len(offer.alternatives)])]
    if not selector.isdigit():
        return [alternative.way for alternative in offer.alternatives if alternative.has_attribute(selector)]
    position = int(selector) - 1
    return [offer.alternatives[position].way] if 0 <= position < len(offer.alternatives) else []


# ---------------------------------------------------------------------------
# The feature names of one variant
# ---------------------------------------------------------------------------

# What every feature name resolves to in a single variant, for each combo needing that feature
FeatureIndex = Mapping[comboid, Mapping[FeatureName, Offer]]
# The needed feature rows of each combo, grouped by the feature they ask for
NeededRows = Mapping[comboid, Mapping[featureid, Sequence[FeatureNeededInCombo]]]


def select_in(index: FeatureIndex, combo_id: comboid | None, name: FeatureName, selector: str | None, surplus: bool = False) -> list[Way]:
    '''What a reference picks in a text of the given combo, which resolves only the features the combo
    needs. A text written on a card has no combo, and resolves nothing.'''
    return select(index.get(combo_id, {}).get(name, Offer()), selector, surplus) if combo_id is not None else []


def needed_rows_by_feature(data: Data, combos: Iterable[Combo]) -> dict[comboid, dict[featureid, list[FeatureNeededInCombo]]]:
    rows = dict[comboid, dict[featureid, list[FeatureNeededInCombo]]]()
    for combo in combos:
        by_feature = rows.setdefault(combo.id, {})
        for row in data.combo_to_needed_features[combo.id]:
            by_feature.setdefault(row.feature_id, []).append(row)
    return rows


def deal(rows: Sequence[FeatureNeededInCombo], accepted: Sequence[Sequence[int]]) -> list[list[int]]:
    '''Which alternatives satisfy each needed feature row of a combo, by position, given the ones each row
    accepts: a row gets one per copy it needs, and no two rows get the same one. Earlier rows get earlier
    alternatives, unless that would leave a later row short of one it accepts.'''
    slots = [index for index, row in enumerate(rows) for _ in range(row.quantity)]
    owners = dict[int, int]()

    def take(slot: int, visited: set[int]) -> bool:
        choices = accepted[slots[slot]]
        free = next((position for position in choices if position not in owners), None)
        if free is not None:
            owners[free] = slot
            return True
        for position in choices:
            if position not in visited:
                visited.add(position)
                if take(owners[position], visited):
                    owners[position] = slot
                    return True
        return False

    for slot in range(len(slots)):
        take(slot, set())
    shares = [list[int]() for _ in rows]
    for position in sorted(owners):
        shares[slots[owners[position]]].append(position)
    return shares


def index_of(
    data: Data,
    needed_rows: NeededRows,
    alternatives: Mapping[FeatureName, Sequence[Alternative]],
) -> tuple[dict[comboid, dict[FeatureName, Offer]], dict[int, list[Way]]]:
    '''What each combo sees of the features it needs, and the ways each of its needed feature rows
    reaches, by row id.

    A combo sees only the alternatives its rows accept, the ones dealt to each row first, in row order:
    that is what makes `[[name$2]]` mean "whatever satisfies the second row" in every variant of that
    combo, and what keeps its texts from naming a card the variant holds for another reason. A row
    reaches the ones dealt to it. The ones dealt to no row are reached by every row accepting them, and
    so is every one a row accepts when it was dealt none, because one candidate satisfies them all.
    '''
    index = dict[comboid, dict[FeatureName, Offer]]()
    reached = dict[int, list[Way]]()
    for combo_id, rows_by_feature in needed_rows.items():
        for feature_id, rows in rows_by_feature.items():
            name = data.id_to_feature[feature_id].name
            offered = alternatives.get(name, ())
            accepted = [{position for position, alternative in enumerate(offered) if data.feature_needed_in_combo_to_attributes_matcher[row.id].matches(alternative.attribute_ids)} for row in rows]
            shares = deal(rows, [sorted(positions) for positions in accepted])
            dealt = [position for share in shares for position in share]
            index.setdefault(combo_id, {})[name] = Offer(
                alternatives=tuple([offered[position] for position in dealt] + [
                    alternative
                    for position, alternative in enumerate(offered)
                    if position not in dealt and any(position in positions for positions in accepted)
                ]),
                dealt=len(dealt),
            )
            for row, share, positions in zip(rows, shares, accepted):
                reached[row.id] = [
                    alternative.way
                    for position, alternative in enumerate(offered)
                    if position in share or ((not share or position not in dealt) and position in positions)
                ]
    return index, reached


# ---------------------------------------------------------------------------
# The ways a variant offers
# ---------------------------------------------------------------------------

def card_number(card: Card) -> int:
    '''The number the ingredients of a variant are keyed by, which every card reaching here carries.'''
    assert card.number is not None
    return card.number


@dataclass(frozen=True)
class IngredientPositions:
    '''Where each ingredient of the variant is displayed. This orders the ways of producing the same
    feature and the names of a way, so that a text names them the way the reader sees them listed.'''
    cards: Mapping[cardid, int] = field(default_factory=dict)
    templates: Mapping[templateid, int] = field(default_factory=dict)

    @property
    def last(self) -> int:
        return len(self.cards) + len(self.templates) + 1

    def of_card(self, card_id: cardid) -> int:
        return self.cards.get(card_id, self.last)

    def of_template(self, template_id: templateid) -> int:
        return len(self.cards) + self.templates.get(template_id, self.last)

    def position_of(self, cards: Iterable[Card], templates: Iterable[Template]) -> tuple[int, ...]:
        positions = [self.of_card(card_number(c)) for c in cards]
        positions.extend(self.of_template(t.id) for t in templates)
        return tuple(sorted(positions))


def attribute_names_of(data: Data, attribute_ids: Iterable[int]) -> tuple[str, ...]:
    return tuple(sorted(data.id_to_feature_attribute[a].name for a in attribute_ids if a in data.id_to_feature_attribute))


def way_alternatives(
    data: Data,
    replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
    positions: IngredientPositions,
) -> dict[FeatureName, list[Alternative]]:
    '''Every way of producing each feature name, offered by the names of the attributes it was produced
    with, an order every variant agrees on, and then in the display order of their ingredients.'''
    by_name = defaultdict[FeatureName, list[Alternative]](list)
    for feature, recipes in replacements.items():
        attribute_names = attribute_names_of(data, feature.attributes)
        by_name[feature.feature.name].extend(
            Alternative(Way(feature, tuple(cards), tuple(templates)), feature.attributes, attribute_names)
            for cards, templates in sorted(recipes, key=lambda recipe: positions.position_of(*recipe))
        )
    return {name: sorted(alternatives, key=lambda a: a.attribute_names) for name, alternatives in by_name.items()}


# ---------------------------------------------------------------------------
# The starting states of the ingredients
# ---------------------------------------------------------------------------

def merge_used_faces(initial_states: Iterable[Ingredient]) -> int | None:
    '''Merges the used faces of the ingredients contributing a card to a variant: a specified face is
    kept only when every contributor that specifies one agrees on the same number (blanks are ignored).'''
    faces = {face for state in initial_states if (face := getattr(state, 'used_face', None)) is not None}
    return faces.pop() if len(faces) == 1 else None


def merge_zone_locations(rows: Sequence[Ingredient]) -> str:
    '''The starting locations the rows contributing an ingredient to a variant agree on: each row keeps
    only the ones it shares with the ones left, and a row sharing none of them leaves them as they were.'''
    zone_locations = rows[0].zone_locations
    for row in rows[1:]:
        zone_locations = ''.join(
            location
            for location in zone_locations
            if location in row.zone_locations
        ) or zone_locations or row.zone_locations
    return zone_locations


def get_default_zone_location_for_card(card: Card) -> ZoneLocation:
    if card.is_of_type(CardType.INSTANT) or card.is_of_type(CardType.SORCERY):
        return ZoneLocation.HAND
    return ZoneLocation.BATTLEFIELD


def default_zone_locations(data: Data, ingredient: CardInVariant | TemplateInVariant) -> str:
    '''Where an ingredient no source asks anything of starts: a card by its type, a template by the
    default of the field.'''
    if isinstance(ingredient, CardInVariant):
        return get_default_zone_location_for_card(data.id_to_card[ingredient.card_id]).value
    return Ingredient._meta.get_field('zone_locations').get_default()  # pyright: ignore[reportAttributeAccessIssue]


@dataclass(frozen=True)
class SourcedState:
    '''One row an ingredient of a variant takes a starting state from, and the source that row comes
    from, which is what lets a reference in that text name it.'''
    source: SourceIndex
    row: Ingredient


@dataclass(frozen=True)
class ByIngredient(Generic[_V]):
    '''Something a variant keeps for each of its ingredients, cards and templates apart because their
    ids are numbered on their own.'''
    cards: Mapping[cardid, _V]
    templates: Mapping[templateid, _V]

    def of(self, ingredient: CardInVariant | TemplateInVariant, default: _V) -> _V:
        if isinstance(ingredient, CardInVariant):
            return self.cards.get(ingredient.card_id, default)
        return self.templates.get(ingredient.template_id, default)


@dataclass(frozen=True)
class InitialStates(ByIngredient[Sequence[SourcedState]]):
    '''The rows every ingredient of a variant inherits its starting state from.'''

    @classmethod
    def collect(cls, data: Data, sources: Sequence[TextSource], positions: IngredientPositions) -> 'InitialStates':
        '''The rows an ingredient inherits from, in source order: the features of the cards first, then
        the rows of the needed combos, in combo order. Only the ingredients the variant ends up with are
        collected, which is what the positions carry.'''
        cards = defaultdict[cardid, list[SourcedState]](list)
        templates = defaultdict[templateid, list[SourcedState]](list)
        for index, source in enumerate(sources):
            if isinstance(source, FeatureOfCard):
                cards[source.card_id].append(SourcedState(index, source))
            elif isinstance(source, Combo):
                for card_in_combo in data.combo_to_cards[source.id]:
                    if card_in_combo.card_id in positions.cards:
                        cards[card_in_combo.card_id].append(SourcedState(index, card_in_combo))
                for template_in_combo in data.combo_to_templates[source.id]:
                    if template_in_combo.template_id in positions.templates:
                        templates[template_in_combo.template_id].append(SourcedState(index, template_in_combo))
        return cls(cards=cards, templates=templates)

    def used_faces(self) -> dict[cardid, int | None]:
        return {card_id: merge_used_faces(state.row for state in states) for card_id, states in self.cards.items()}


@dataclass(frozen=True)
class UsedFaces:
    '''The face a text names each card of a variant by. Rows disagreeing on the face of a card leave
    the whole card to the variant, since it is used by more than one face, while a feature it produces
    is still named by the face the rows producing that feature agree on.'''
    of_cards: Mapping[cardid, int | None]
    of_producers: Mapping[tuple[featureid, cardid], int | None]

    @classmethod
    def collect(cls, data: Data, sources: Sequence[TextSource], initial_states: InitialStates) -> 'UsedFaces':
        rows = defaultdict[tuple[featureid, cardid], list[Ingredient]](list)
        for card_id, states in initial_states.cards.items():
            for state in states:
                for feature_id, _ in produced_features(data, sources[state.source]):
                    rows[feature_id, card_id].append(state.row)
        return cls(
            of_cards=initial_states.used_faces(),
            of_producers={key: merge_used_faces(producing) for key, producing in rows.items()},
        )

    def of(self, card_id: cardid, feature_id: featureid | None) -> int | None:
        face = self.of_producers.get((feature_id, card_id)) if feature_id is not None else None
        return face if face is not None else self.of_cards.get(card_id)


@dataclass
class NeededFeatureOverride:
    '''What the needed feature rows an ingredient replaces ask of it: the rows themselves, whose card
    states are written instead of the ones the combos it appears in ask for, and how many times each
    starting location was asked for, so that the ones the most requests agree on win.'''
    rows: list[FeatureNeededInCombo] = field(default_factory=list)
    location_requests: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))

    def add(self, row: FeatureNeededInCombo) -> None:
        '''Asks the row of this ingredient, once per way of replacing the feature it needs: the row is
        kept once, in the order it is asked in, while every request counts towards its locations.'''
        if row not in self.rows:
            self.rows.append(row)
        for location in row.zone_locations:
            self.location_requests[location] += 1

    def zone_locations(self) -> str:
        '''The locations the most requests agree on, or none when nothing was asked of the ingredient.'''
        score = max(self.location_requests.values(), default=0)
        return ''.join(location for location, count in self.location_requests.items() if count == score) if score else ''


@dataclass(frozen=True)
class NeededFeatureOverrides(ByIngredient[NeededFeatureOverride]):
    '''What the needed feature rows of a variant ask of the ingredients replacing the features they
    need, which overrides what those ingredients inherit from the combos they appear in.'''

    @classmethod
    def collect(cls, data: Data, needed_combos: Sequence[Combo], reached: Mapping[int, Sequence[Way]]) -> 'NeededFeatureOverrides':
        '''What every needed feature row asking for a starting location reaches: the ingredients the ways
        satisfying it name, so that two rows of a combo needing the same feature each start their own.
        The rows are met combo by combo, in the order each combo asks for them, which is the order their
        states are written in.'''
        cards = defaultdict[cardid, NeededFeatureOverride](NeededFeatureOverride)
        templates = defaultdict[templateid, NeededFeatureOverride](NeededFeatureOverride)
        for combo in needed_combos:
            for row in data.combo_to_needed_features[combo.id]:
                if not row.zone_locations:
                    continue
                for way in reached.get(row.id, ()):
                    for item in way.named():
                        if item.card is not None:
                            cards[card_number(item.card)].add(row)
                        elif item.template is not None:
                            templates[item.template.id].add(row)
        return cls(cards=cards, templates=templates)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def join_texts(texts: Iterable[str]) -> str:
    '''How the texts of a field are combined into one, both where a reference writes them and where
    they are appended to each other.'''
    return '\n'.join(texts)


def merge_of(key: Key) -> MergeTexts:
    '''How the texts of a field are combined where a reference of another field writes them.'''
    if key == 'mana_needed':
        return merge_mana_costs
    if key in CARD_STATE_KEYS:
        return join_with_conjunction
    return join_texts


# Private use characters, which no text can hold, mark in a field being written where each line of its
# texts landed and which line each line reference points at, until the whole field is numbered at once
LINE_MARK = ''
TARGET_MARK = ''
MARK_END = ''
DELETION_MARK = ''
LINE_MARK_PATTERN = re.compile(f'{LINE_MARK}\\d+{MARK_END}')
TARGET_MARK_PATTERN = re.compile(f'{TARGET_MARK}(\\d+){MARK_END}')
LEADING_BLANK_PATTERN = re.compile(f'^(?:{LINE_MARK}\\d+{MARK_END}|\\s)+')
TRAILING_BLANK_PATTERN = re.compile(f'(?:{LINE_MARK}\\d+{MARK_END}|\\s)+$')


def line_marks(text: str) -> str:
    '''The marks of the lines that landed on a piece of text, to move along when the piece goes away.'''
    return ''.join(LINE_MARK_PATTERN.findall(text))


def is_blank(text: str) -> bool:
    return not LINE_MARK_PATTERN.sub('', text).replace(DELETION_MARK, '').strip()


@dataclass(frozen=True)
class FieldAssembly:
    '''Assembles one text field of a variant, out of the texts its sources wrote for it.

    A reference to the key of the field itself writes the texts of the sources it names in place, which
    are then left out of the result, because they have already been written where they were mentioned.
    Deciding that is why a whole field is assembled at once: a field naming no source is simply every
    text of it, merged. Every other reference is written inline, and a reference with nothing to write
    is deleted instead, so that no variant displays one. A reference to a feature its combo does not
    need, which the admin refuses, is no such reference: it stays as written, for an editor to spot.

    A source listed in only_when_included never writes on its own: its text reaches the field only
    where a reference of a written text names it.

    A line reference is replaced with the line of the field that the line it points at landed on, which
    only the whole field knows: every writing of a text marks its own lines before anything is written
    into it, and the field numbers them all at once. The fields joining their texts line by line are the
    only ones whose lines are counted, and only when one of their texts points at a line.
    '''
    key: Key
    # with their aliases expanded
    texts: Mapping[SourceIndex, str]
    merge: MergeTexts
    named_by: Callable[[SourceIndex, re.Match[str]], Sequence[SourceIndex]]
    known: Callable[[SourceIndex, re.Match[str]], bool]
    substitute: Callable[[str, SourceIndex], str]
    only_when_included: frozenset[SourceIndex] = frozenset()
    line_ids: Iterator[int] = field(default_factory=count)

    @cached_property
    def numbered(self) -> bool:
        return self.merge is join_texts and any(LINE_REFERENCE_PATTERN.search(text) for text in self.texts.values())

    def assemble(self) -> str:
        text = self.write_all((source for source in self.texts if source not in self.included_sources and source not in self.only_when_included), frozenset())
        if not self.numbered:
            return text
        landed = {mark[1:-1]: str(number) for number, line in enumerate(text.split('\n'), start=1) for mark in LINE_MARK_PATTERN.findall(line)}
        return LINE_MARK_PATTERN.sub('', TARGET_MARK_PATTERN.sub(lambda target: landed[target[1]], text))

    def write_all(self, sources: Iterable[SourceIndex], ancestors: frozenset[SourceIndex]) -> str:
        '''Writes the given sources and merges their texts the way the field does, leaving out the empty ones.'''
        return self.merge(text for text in (self.write(source, ancestors) for source in sources) if text)

    def includes(self, reference: re.Match[str]) -> bool:
        return key_of(reference) == self.key

    def named(self, source: SourceIndex, reference: re.Match[str]) -> list[SourceIndex]:
        '''The sources a reference to this field names, never the one writing it: a text does not write
        itself, so the sole producer of a feature its own text mentions has nothing to write there.'''
        return [other for other in self.named_by(source, reference) if other != source]

    @cached_property
    def included_sources(self) -> frozenset[SourceIndex]:
        '''Every source a reference of a written text names, which is what keeps its text from being
        appended on its own. A text is written when its source writes on its own or when it is
        included, so the references of a text written nowhere name nothing.'''
        written = [source for source in self.texts if source not in self.only_when_included]
        included = set[SourceIndex]()
        while written:
            source = written.pop()
            for reference in FEATURE_REFERENCE_PATTERN.finditer(self.texts[source]):
                if self.includes(reference):
                    for other in self.named(source, reference):
                        if other not in included:
                            included.add(other)
                            if other in self.texts and other in self.only_when_included:
                                written.append(other)
        return frozenset(included)

    @cached_property
    def written_sources(self) -> frozenset[SourceIndex]:
        '''The sources whose text the field writes, on their own or where they are included.'''
        return frozenset(source for source in self.texts if source not in self.only_when_included or source in self.included_sources)

    def write(self, source: SourceIndex, ancestors: frozenset[SourceIndex]) -> str:
        '''The text of one source, with its references written out. A source already being written higher
        up is skipped, so that a cycle of references terminates. A reference left with nothing to write,
        because it names no source or only sources being written already, is deleted without touching the
        text around it, and a line it leaves empty is dropped: the text it was deleted from is then
        trimmed, lines along with it. The marks of a dropped line move to the line taking its place, and
        the ones trimmed away to the nearest line kept.'''
        written = ancestors | {source}

        def include(reference: re.Match[str]) -> str:
            if not self.includes(reference) or not self.known(source, reference):
                return reference[0]
            return self.write_all((other for other in self.named(source, reference) if other not in written), written) or DELETION_MARK

        text = FEATURE_REFERENCE_PATTERN.sub(include, self.substitute(self.marked(self.texts.get(source, '')), source))
        if DELETION_MARK not in text:
            return text
        kept = list[str]()
        moving = ''
        for line in text.split('\n'):
            if DELETION_MARK in line and is_blank(line):
                moving += line_marks(line)
            else:
                kept.append(moving + line.replace(DELETION_MARK, ''))
                moving = ''
        text = '\n'.join(kept) + moving
        if is_blank(text):
            return ''
        text = LEADING_BLANK_PATTERN.sub(lambda blank: line_marks(blank[0]), text)
        return TRAILING_BLANK_PATTERN.sub(lambda blank: line_marks(blank[0]), text)

    def marked(self, text: str) -> str:
        '''One writing of a text, with each line marked by an id of its own and each line reference
        pointing at the id of the line it means, for the field to number. A reference pointing outside of
        the text is left as written, and so is a text in a field whose lines are not counted.'''
        if not self.numbered or not text:
            return text
        lines = text.split('\n')
        ids = [next(self.line_ids) for _ in lines]

        def target(reference: re.Match[str], line: int) -> str:
            pointed = referenced_line(reference, line)
            return f'{TARGET_MARK}{ids[pointed - 1]}{MARK_END}' if 1 <= pointed <= len(lines) else reference[0]

        return '\n'.join(
            f'{LINE_MARK}{ids[index]}{MARK_END}' + LINE_REFERENCE_PATTERN.sub(lambda reference: target(reference, index + 1), line)
            for index, line in enumerate(lines)
        )


class VariantContext:
    '''Renders the ingredients and the texts of a single variant, resolving the references they hold.

    The texts come from the sources of the variant, the features of its cards followed by the combos it
    needs, each followed by the texts their dictionaries write, and each identified by its position
    among them. That numbering spans every field, so one context is built per variant and reused by all
    of them, along with everything else derived from the same sources: what each feature provides, which
    texts the variant writes on its own, what the ingredients start as, and what the needed feature rows
    ask of them.
    '''

    def __init__(
        self,
        data: Data,
        index: FeatureIndex,
        sources: Sequence[TextSource],
        written_by_default: Mapping[Key, frozenset[SourceIndex]],
        used_faces: UsedFaces,
        initial_states: InitialStates,
        overrides: NeededFeatureOverrides,
    ) -> None:
        self.data = data
        self.index = index
        self.sources = sources
        self.written_by_default = written_by_default
        self.used_faces = used_faces
        self.initial_states = initial_states
        self.overrides = overrides
        self.source_combo_ids = [owning_combo_id(source) for source in sources]
        self.source_of_combo = {source.id: index for index, source in enumerate(sources) if isinstance(source, Combo)}

    @classmethod
    def build(
        cls,
        data: Data,
        replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
        generator_combos: Sequence[Combo],
        other_combos: Sequence[Combo],
        needed_feature_of_cards: Sequence[FeatureOfCard],
        positions: IngredientPositions = IngredientPositions(),
    ) -> 'VariantContext':
        '''Builds the context of a variant from the ways of producing its features, its sources and where
        its ingredients are displayed. The states collected for a card give the face it is used by, which
        is what makes a card used by one face show that half of its name.'''
        needed_combos = [*generator_combos, *other_combos]
        sources, overrides = collect_sources(data, needed_feature_of_cards, needed_combos)
        initial_states = InitialStates.collect(data, sources, positions)
        builder = DictionaryBuilder(data, sources, overrides, positions)
        alternatives = way_alternatives(data, replacements, positions)
        for offered in alternatives.values():
            for alternative in offered:
                builder.walk(alternative.way)
        index, reached = index_of(data, needed_rows_by_feature(data, needed_combos), alternatives)
        roots = roots_of(data, sources, {combo.id for combo in generator_combos})
        return cls(
            data=data,
            index=index,
            sources=sources,
            written_by_default={key: builder.written_by_default(roots, key) for key in TEXT_KEYS},
            used_faces=UsedFaces.collect(data, sources, initial_states),
            initial_states=initial_states,
            overrides=NeededFeatureOverrides.collect(data, needed_combos, reached),
        )

    def knows(self, combo_id: comboid | None, reference: re.Match[str]) -> bool:
        '''Whether a reference in a text of the given combo names a feature the combo needs.'''
        return combo_id is not None and reference['feature'] in self.index.get(combo_id, {})

    def known(self, source: SourceIndex, reference: re.Match[str]) -> bool:
        return self.knows(self.source_combo_ids[source], reference)

    def value(self, combo_id: comboid | None, reference: re.Match[str]) -> tuple[Value, list[Way]]:
        '''What a reference in a text of the given combo resolves to, and the ways it selected. A text of
        the variant takes the surplus too, which it would otherwise append on its own.'''
        ways = select_in(self.index, combo_id, reference['feature'], reference['selector'], key_of(reference) in TEXT_KEYS)
        return combine(way.dictionary for way in ways).get(key_of(reference), EMPTY_VALUE), ways

    def named_by(self, source: SourceIndex, reference: re.Match[str]) -> list[SourceIndex]:
        '''The sources a reference to a field names: the texts the selected ways provide for it, or for a
        starting state, every source producing something on those ways.'''
        value, ways = self.value(self.source_combo_ids[source], reference)
        if key_of(reference) in CARD_STATE_KEYS:
            return sorted({other for way in ways for other in way.sources})
        return sources_of(value)

    def name(self, value: Value, reference: re.Match[str], ways: Sequence[Way], depth: int) -> str:
        '''Writes what a key other than a text of a variant holds, joined as a sentence. A lone card is
        named by the face the reference asks for, or else by the one it is used by.'''
        face = int(reference['face']) if reference['face'] else None
        items = value.items
        if face is not None and len(items) == 1 and (card := items[0].card) is not None and 1 <= face <= card.faces:
            return card.face_name(face, short=True)
        feature_id = ways[0].feature.feature.id if ways else None

        def written(item: Item) -> str:
            if item.card is not None:
                return item.card.face_name(self.used_faces.of(card_number(item.card), feature_id), short=True)
            if item.template is not None:
                return item.template.name
            return self.substitute(expand_aliases(item.text), item.combo_id, None, depth + 1).replace(DELETION_MARK, '')

        return join_with_conjunction(map(written, items))

    def substitute(self, text: str, combo_id: comboid | None, key: Key | None, depth: int = 0) -> str:
        '''Writes inline every reference of a text but the ones to the key of the field being assembled:
        a text of another field is assembled right there, anything else is written as a sentence, and a
        reference resolving to nothing becomes a deletion. A reference to a feature the combo does not
        need stays as written.'''
        def replace(reference: re.Match[str]) -> str:
            referenced = key_of(reference)
            if referenced == key or not self.knows(combo_id, reference):
                return reference[0]
            if depth > MAX_REFERENCE_DEPTH or referenced in CARD_STATE_KEYS:
                return DELETION_MARK
            value, ways = self.value(combo_id, reference)
            if referenced in TEXT_KEYS:
                written = self.assembly(referenced, {source: expand_aliases(text_of(self.sources[source], referenced)) for source in sources_of(value)}, merge_of(referenced), frozenset(), depth + 1).assemble()
            else:
                written = self.name(value, reference, ways, depth)
            return written or DELETION_MARK

        return FEATURE_REFERENCE_PATTERN.sub(replace, text)

    def apply(self, text: str, combo_id: comboid | None = None) -> str:
        '''Writes every reference of a single text inline, the ones its aliases stand for included, the
        way a text of no field would be: a reference resolving to nothing writes nothing, while one to a
        feature the combo does not need stays as written.'''
        return self.substitute(expand_aliases(text), combo_id, None).replace(DELETION_MARK, '')

    def assembly(self, key: Key, texts: Mapping[SourceIndex, str], merge: MergeTexts, only_when_included: frozenset[SourceIndex] = frozenset(), depth: int = 0) -> FieldAssembly:
        return FieldAssembly(
            key=key,
            texts={source: text for source, text in texts.items() if text},
            merge=merge,
            named_by=self.named_by,
            known=self.known,
            substitute=lambda text, source: self.substitute(text, self.source_combo_ids[source], key, depth),
            only_when_included=only_when_included,
        )

    def texts_by_source(self, states: Sequence[SourcedState], field: str) -> dict[SourceIndex, str]:
        '''What the given rows write for one field, grouped by the source each row comes from, in row
        order: two rows of the same source write a single text.'''
        texts = dict[SourceIndex, str]()
        for state in states:
            if text := expand_aliases(getattr(state.row, field)):
                texts[state.source] = join_texts([texts[state.source], text]) if state.source in texts else text
        return texts

    def render_ingredient(self, ingredient: CardInVariant | TemplateInVariant) -> None:
        '''Writes everything an ingredient of the variant inherits from its sources: where it starts,
        whether it must be the commander, which face it is used by, and its starting card states, each
        assembled the way the text fields of the variant are, so that a reference to the same state
        writes the state another source asks the same ingredient for. What the needed feature rows it
        replaces ask of it comes first, both for the locations and for the states, and an ingredient no
        source asks anything of falls back to the defaults of its kind.'''
        states = self.initial_states.of(ingredient, ())
        rows = [state.row for state in states]
        asked = self.overrides.of(ingredient, NeededFeatureOverride())
        asked_states = [SourcedState(self.source_of_combo[row.combo_id], row) for row in asked.rows]
        inherited_locations = merge_zone_locations(rows) if rows else default_zone_locations(self.data, ingredient)
        ingredient.zone_locations = asked.zone_locations() or inherited_locations
        ingredient.must_be_commander = any(row.must_be_commander for row in rows)
        if isinstance(ingredient, CardInVariant):
            ingredient.used_face = merge_used_faces(rows)
        for location, state_field in Ingredient.CARD_STATE_FIELDS.items():
            if location not in ingredient.zone_locations:
                setattr(ingredient, state_field, '')
                continue
            overriding = [state for state in asked_states if location in state.row.zone_locations and getattr(state.row, state_field)]
            setattr(ingredient, state_field, self.assembly(
                state_field,
                self.texts_by_source(overriding or states, state_field),
                join_texts if overriding else join_with_conjunction,
            ).assemble())

    def field_assembly(self, field: str, merge: MergeTexts = join_texts) -> FieldAssembly:
        '''One text field of the variant, out of what each of its sources wrote for it, in source order.
        A source with nothing to say writes nothing, and one the variant does not write on its own writes
        only where it is included.'''
        texts = {index: expand_aliases(text) for index, source in enumerate(self.sources) if (text := text_of(source, field))}
        written = self.written_by_default.get(field)
        left_out = frozenset(index for index in texts if index not in written) if written is not None else frozenset()
        return self.assembly(field, texts, merge, left_out)

    def render_field(self, field: str, merge: MergeTexts = join_texts) -> str:
        return self.field_assembly(field, merge).assemble()
