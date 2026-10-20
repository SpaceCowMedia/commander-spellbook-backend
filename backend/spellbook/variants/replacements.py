import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cached_property
from itertools import count
from typing import Callable, Generic, Iterable, Iterator, Mapping, Sequence, TypeVar
from .variant_data import Data
from .variant_set import cardid, templateid
from .combo_graph import FeatureWithAttributes, comboid, featureid
from spellbook.models import Card, CardInVariant, CardType, Combo, FeatureNeededInCombo, FeatureOfCard, Ingredient, Template, TemplateInVariant, ZoneLocation, join_with_conjunction
from spellbook.models.references import FEATURE_INCLUSION_PATTERN, FEATURE_REPLACEMENT_PATTERN, LINE_REFERENCE_PATTERN, expand_aliases, referenced_line


FeatureName = str
# Position of a source among the ones a variant takes its texts from
SourceIndex = int
# A text of a variant is written either by a combo it needs or by a feature of one of its cards
TextSource = Combo | FeatureOfCard
# How the several texts of one field are combined into the single text of the variant
MergeTexts = Callable[[Iterable[str]], str]
Recipe = tuple[list[Card], list[Template]]

_C = TypeVar('_C')
_V = TypeVar('_V')


# ---------------------------------------------------------------------------
# What a feature name resolves to
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Replacement:
    '''What `[[name]]` is replaced with: the names of the ingredients producing the feature. The card
    behind a lone one is kept, so that a face override in the text can still resolve to a face name.'''
    text: str
    card: Card | None = None

    def resolve(self, face: int | None) -> str:
        if face is not None and self.card is not None and 1 <= face <= self.card.faces:
            return self.card.face_name(face, short=True)
        return self.text


@dataclass(frozen=True)
class Alternative(Generic[_C]):
    '''One of the things a feature name resolves to in a variant, and the attributes the feature was
    produced with. Alternatives are what an attribute selector picks between and what a needed feature
    row is matched against; a positional selector counts through their candidates instead, because one
    alternative can be produced in more than one way.'''
    candidates: tuple[_C, ...]
    attribute_ids: frozenset[int] = frozenset()
    # sorted, in their original case: they order the alternatives of a feature and answer a selector
    attribute_names: tuple[str, ...] = ()

    def has_attribute(self, name: str) -> bool:
        return any(attribute.casefold() == name.casefold() for attribute in self.attribute_names)


def candidates_of(alternatives: Iterable[Alternative[_C]]) -> list[_C]:
    return [candidate for alternative in alternatives for candidate in alternative.candidates]


def select(alternatives: Sequence[Alternative[_C]], selector: str | None) -> Sequence[_C]:
    '''What a selector picks among the alternatives of a feature: an attribute name keeps the ones the
    feature was produced with it, a number counts through their candidates, and no selector keeps them
    all. Nothing selected means the text has nothing to resolve to: a replacement stays as it was
    written, while an inclusion is deleted.'''
    if selector is None:
        return candidates_of(alternatives)
    if not selector.isdigit():
        return candidates_of(alternative for alternative in alternatives if alternative.has_attribute(selector))
    position = int(selector) - 1
    candidates = candidates_of(alternatives)
    return candidates[position:position + 1] if position >= 0 else []


# ---------------------------------------------------------------------------
# The feature names of one variant
# ---------------------------------------------------------------------------

class FeatureIndex(Generic[_C]):
    '''What every feature name resolves to in a single variant.

    A name can offer several alternatives, so the order they come in decides what a positional selector
    points at. A combo needing the same feature more than once gets its own order, following its needed
    feature rows, which is what makes `[[name$2]]` mean "whatever satisfies the second row" in every
    variant of that combo rather than something different in each.
    '''

    def __init__(
        self,
        base: Mapping[FeatureName, Sequence[Alternative[_C]]],
        per_combo: Mapping[comboid, Mapping[FeatureName, Sequence[Alternative[_C]]]],
    ) -> None:
        self.base = base
        self.per_combo = per_combo

    def alternatives(self, name: FeatureName, combo_id: comboid | None) -> Sequence[Alternative[_C]]:
        for_combo = self.per_combo.get(combo_id) if combo_id is not None else None
        if for_combo is not None and name in for_combo:
            return for_combo[name]
        return self.base.get(name, ())

    def select(self, name: FeatureName, selector: str | None, combo_id: comboid | None) -> Sequence[_C]:
        return select(self.alternatives(name, combo_id), selector)


def needed_rows_by_feature(data: Data, combos: Iterable[Combo]) -> dict[featureid, list[FeatureNeededInCombo]]:
    '''The needed feature rows of the given combos, grouped by the feature they ask for.'''
    rows = dict[featureid, list[FeatureNeededInCombo]]()
    for combo in combos:
        for row in data.combo_to_needed_features[combo.id]:
            rows.setdefault(row.feature_id, []).append(row)
    return rows


def matched_first(
    data: Data,
    rows: Iterable[FeatureNeededInCombo],
    alternatives: Sequence[Alternative[_C]],
) -> list[Alternative[_C]]:
    '''The alternatives a combo asks for, first: each needed feature row takes the ones its attributes
    match that no earlier row took, in row order. The ones no row asks for stay reachable after them.'''
    ordered = list[Alternative[_C]]()
    taken = set[int]()
    for row in rows:
        matcher = data.feature_needed_in_combo_to_attributes_matcher[row.id]
        for position, alternative in enumerate(alternatives):
            if position not in taken and matcher.matches(alternative.attribute_ids):
                taken.add(position)
                ordered.append(alternative)
    ordered.extend(a for position, a in enumerate(alternatives) if position not in taken)
    return ordered


def index_of(
    data: Data,
    needed_combos: Sequence[Combo],
    alternatives: Mapping[FeatureName, Sequence[Alternative[_C]]],
) -> FeatureIndex[_C]:
    '''Indexes the alternatives of every feature name, adding the order each combo sees them in. Only a
    feature offering more than one alternative can be ordered differently, so only those are stored.'''
    per_combo = dict[comboid, Mapping[FeatureName, Sequence[Alternative[_C]]]]()
    for combo in needed_combos:
        for_combo = dict[FeatureName, Sequence[Alternative[_C]]]()
        for feature_id, rows in needed_rows_by_feature(data, [combo]).items():
            name = data.id_to_feature[feature_id].name
            offered = alternatives.get(name, ())
            if len(offered) > 1:
                for_combo[name] = matched_first(data, rows, offered)
        if for_combo:
            per_combo[combo.id] = for_combo
    return FeatureIndex(alternatives, per_combo)


# ---------------------------------------------------------------------------
# The two kinds of alternative a variant offers
# ---------------------------------------------------------------------------

def card_number(card: Card) -> int:
    '''The number the ingredients of a variant are keyed by, which every card reaching here carries.'''
    assert card.number is not None
    return card.number


@dataclass(frozen=True)
class IngredientPositions:
    '''Where each ingredient of the variant is displayed. This orders the ways of producing the same
    feature, so that a text names them the way the reader sees them listed.'''
    cards: Mapping[cardid, int] = field(default_factory=dict)
    templates: Mapping[templateid, int] = field(default_factory=dict)

    def position_of(self, cards: Iterable[Card], templates: Iterable[Template]) -> tuple[int, ...]:
        last = len(self.cards) + len(self.templates) + 1
        positions = [self.cards.get(card_number(c), last) for c in cards]
        positions.extend(len(self.cards) + self.templates.get(t.id, last) for t in templates)
        return tuple(sorted(positions))


def attribute_names_of(data: Data, attribute_ids: Iterable[int]) -> tuple[str, ...]:
    return tuple(sorted(data.id_to_feature_attribute[a].name for a in attribute_ids if a in data.id_to_feature_attribute))


def is_asked_for(data: Data, feature: FeatureWithAttributes, rows: Sequence[FeatureNeededInCombo]) -> bool:
    '''Whether any combo needing that feature accepts the attributes it was produced with. What no
    combo asks for is not offered as a replacement, even though the variant produces it.'''
    return not rows or any(
        data.feature_needed_in_combo_to_attributes_matcher[row.id].matches(feature.attributes)
        for row in rows
    )


def replacement_of(recipe: Recipe, used_faces: 'UsedFaces', feature_id: featureid) -> Replacement:
    '''The name a text shows for one way of producing a feature. A card used by one of its faces shows
    that half of its name, and a lone card is kept, so that a face override in the text still resolves.'''
    cards, templates = recipe
    names = [c.face_name(used_faces.of(card_number(c), feature_id), short=True) for c in cards] + [t.name for t in templates]
    return Replacement(
        text=' + '.join(names),
        card=cards[0] if len(cards) == 1 and not templates else None,
    )


def replacement_alternatives(
    data: Data,
    replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
    needed_combos: Sequence[Combo],
    used_faces: 'UsedFaces',
    positions: IngredientPositions,
) -> dict[FeatureName, list[Alternative[Replacement]]]:
    '''What every feature name is replaced with, one alternative per set of attributes it was produced
    with, holding the ways of producing it in the display order of the ingredients they name.'''
    rows = needed_rows_by_feature(data, needed_combos)
    by_name = defaultdict[FeatureName, list[Alternative[Replacement]]](list)
    for feature, recipes in replacements.items():
        if not is_asked_for(data, feature, rows.get(feature.feature.id, [])):
            continue
        by_name[feature.feature.name].append(Alternative(
            candidates=tuple(
                replacement_of(recipe, used_faces, feature.feature.id)
                for recipe in sorted(recipes, key=lambda recipe: positions.position_of(*recipe))
            ),
            attribute_ids=feature.attributes,
            attribute_names=attribute_names_of(data, feature.attributes),
        ))
    # the alternatives of a feature are offered by attribute name, an order every variant agrees on
    return {name: sorted(alternatives, key=lambda a: a.attribute_names) for name, alternatives in by_name.items()}


def produced_features(data: Data, source: TextSource) -> Iterable[tuple[featureid, frozenset[int]]]:
    '''The features a source produces, with the attributes it produces them with.'''
    if isinstance(source, Combo):
        return [
            (row.feature_id, frozenset(data.feature_produced_in_combo_to_attributes[row.id]))
            for row in data.combo_to_produced_features[source.id]
        ]
    return [(source.feature_id, frozenset(data.feature_of_card_to_attributes[source.id]))]


def producer_alternatives(data: Data, sources: Sequence[TextSource]) -> dict[FeatureName, list[Alternative[SourceIndex]]]:
    '''Which sources produce every feature name, one alternative each, in the order their texts are
    collected. A source producing the same feature through more than one row is a single alternative,
    carrying every attribute it produced it with.'''
    attribute_ids = defaultdict[FeatureName, dict[SourceIndex, frozenset[int]]](dict)
    for index, source in enumerate(sources):
        for feature_id, attributes in produced_features(data, source):
            name = data.id_to_feature[feature_id].name
            attribute_ids[name][index] = attribute_ids[name].get(index, frozenset()) | attributes
    return {
        name: [
            Alternative(candidates=(index,), attribute_ids=attributes, attribute_names=attribute_names_of(data, attributes))
            for index, attributes in by_source.items()
        ]
        for name, by_source in attribute_ids.items()
    }


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
    from, which is what lets an inclusion in that text name it.'''
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
                continue
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

    def of(self, card_id: cardid, feature_id: featureid) -> int | None:
        face = self.of_producers.get((feature_id, card_id))
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
    def collect(
        cls,
        data: Data,
        replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
        needed_combos: Sequence[Combo],
    ) -> 'NeededFeatureOverrides':
        '''What every needed feature row asking for a starting location reaches: every ingredient naming
        the feature it needs, produced with attributes it accepts. The rows are met combo by combo, in
        the order each combo asks for them, which is the order their states are written in.'''
        cards = defaultdict[cardid, NeededFeatureOverride](NeededFeatureOverride)
        templates = defaultdict[templateid, NeededFeatureOverride](NeededFeatureOverride)
        for combo in needed_combos:
            for row in data.combo_to_needed_features[combo.id]:
                if not row.zone_locations:
                    continue
                matcher = data.feature_needed_in_combo_to_attributes_matcher[row.id]
                for feature, recipes in replacements.items():
                    if feature.feature.id != row.feature_id or not matcher.matches(feature.attributes):
                        continue
                    for recipe_cards, recipe_templates in recipes:
                        for card in recipe_cards:
                            assert card.number is not None
                            cards[card.number].add(row)
                        for template in recipe_templates:
                            templates[template.id].add(row)
        return cls(cards=cards, templates=templates)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def join_texts(texts: Iterable[str]) -> str:
    '''How the texts of a field are combined into one, both where an inclusion writes them and where
    they are appended to each other.'''
    return '\n'.join(texts)


def owning_combo_id(source: TextSource) -> comboid | None:
    '''The combo a source resolves its feature names against: a text written on a card has none.'''
    return source.id if isinstance(source, Combo) else None


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

    An inclusion is replaced with the texts of the sources it names, which are then left out of the
    result, because they have already been written where they were mentioned. Deciding that is why a
    whole field is assembled at once: a field holding no inclusion is simply every text of it, merged.
    An inclusion with nothing to write is deleted instead, so that no variant displays one.

    A source listed in only_when_included never writes on its own: its text reaches the field only
    where an inclusion names it, and so do the inclusions that text holds.

    A line reference is replaced with the line of the field that the line it points at landed on, which
    only the whole field knows: every writing of a text marks its own lines, and the field numbers them
    all at once. The fields joining their texts line by line are the only ones whose lines are counted,
    and only when one of their texts points at a line.
    '''
    producers: FeatureIndex[SourceIndex]
    combo_ids: Sequence[comboid | None]
    texts: Mapping[SourceIndex, str]
    merge: MergeTexts
    only_when_included: frozenset[SourceIndex] = frozenset()
    line_ids: Iterator[int] = field(default_factory=count)

    @cached_property
    def numbered(self) -> bool:
        return self.merge is join_texts and any(LINE_REFERENCE_PATTERN.search(text) for text in self.texts.values())

    def assemble(self) -> str:
        included = self.included_sources()
        text = self.write_all((source for source in self.texts if source not in included and source not in self.only_when_included), frozenset())
        if not self.numbered:
            return text
        landed = {mark[1:-1]: str(number) for number, line in enumerate(text.split('\n'), start=1) for mark in LINE_MARK_PATTERN.findall(line)}
        return LINE_MARK_PATTERN.sub('', TARGET_MARK_PATTERN.sub(lambda target: landed[target[1]], text))

    def write_all(self, sources: Iterable[SourceIndex], ancestors: frozenset[SourceIndex]) -> str:
        '''Writes the given sources and merges their texts the way the field does, leaving out the empty ones.'''
        return self.merge(text for text in (self.write(source, ancestors) for source in sources) if text)

    def named_by(self, source: SourceIndex, inclusion: re.Match[str]) -> list[SourceIndex]:
        '''The sources an inclusion names, never the one writing it: a text does not write itself, so
        the sole producer of a feature its own text mentions has nothing to write there.'''
        return [other for other in self.producers.select(inclusion['key'], inclusion['selector'], self.combo_ids[source]) if other != source]

    def included_sources(self) -> set[SourceIndex]:
        '''Every source named by an inclusion the field ends up writing, which is what keeps its text
        from being appended on its own. The search starts at the sources that write on their own and
        follows the ones they name, so that an inclusion held by a text nothing writes names nothing.'''
        included = set[SourceIndex]()
        pending = [source for source in self.texts if source not in self.only_when_included]
        while pending:
            source = pending.pop()
            for inclusion in FEATURE_INCLUSION_PATTERN.finditer(self.texts.get(source, '')):
                for other in self.named_by(source, inclusion):
                    if other not in included:
                        included.add(other)
                        pending.append(other)
        return included

    def write(self, source: SourceIndex, ancestors: frozenset[SourceIndex]) -> str:
        '''The text of one source, with its inclusions written out in place. A source already being
        written higher up is skipped, so that a cycle of inclusions terminates. An inclusion left with
        nothing to write, because it names no source or only sources being written already, is deleted
        without touching the text around it, and a line it leaves empty is dropped: the text it was
        deleted from is then trimmed, lines along with it. The marks of a dropped line move to the line
        taking its place, and the ones trimmed away to the nearest line kept.'''
        written = ancestors | {source}

        def include(inclusion: re.Match[str]) -> str:
            return self.write_all((other for other in self.named_by(source, inclusion) if other not in written), written) or DELETION_MARK

        text = FEATURE_INCLUSION_PATTERN.sub(include, self.marked(self.texts.get(source, '')))
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
    '''Renders the ingredients and the texts of a single variant, resolving the feature names they
    mention.

    The texts come from the sources of the variant, the features of its cards followed by the combos it
    needs, each identified by its position among them. That numbering spans every field, so one context
    is built per variant and reused by all of them, along with everything else derived from the same
    sources: what replaces a feature name, which sources produce it, what the ingredients start as, and
    what the needed feature rows ask of them.
    '''

    def __init__(
        self,
        data: Data,
        replacements: FeatureIndex[Replacement],
        producers: FeatureIndex[SourceIndex],
        sources: Sequence[TextSource],
        initial_states: InitialStates,
        overrides: NeededFeatureOverrides,
    ) -> None:
        self.data = data
        self.replacements = replacements
        self.producers = producers
        self.sources = sources
        self.initial_states = initial_states
        self.overrides = overrides
        self.source_combo_ids = [owning_combo_id(source) for source in sources]
        self.source_of_combo = {combo_id: index for index, combo_id in enumerate(self.source_combo_ids) if combo_id is not None}
        self.feature_of_card_sources = frozenset(index for index, source in enumerate(sources) if isinstance(source, FeatureOfCard))

    @classmethod
    def build(
        cls,
        data: Data,
        replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
        needed_combos: Sequence[Combo],
        needed_feature_of_cards: Sequence[FeatureOfCard],
        positions: IngredientPositions = IngredientPositions(),
    ) -> 'VariantContext':
        '''Builds the context of a variant from its replacements, its sources and where its ingredients
        are displayed. The states collected for a card give the face it is used by, which is what makes
        a card used by one face show that half of its name.'''
        sources: list[TextSource] = [*needed_feature_of_cards, *needed_combos]
        initial_states = InitialStates.collect(data, sources, positions)
        return cls(
            data=data,
            replacements=index_of(data, needed_combos, replacement_alternatives(
                data, replacements, needed_combos, UsedFaces.collect(data, sources, initial_states), positions,
            )),
            producers=index_of(data, needed_combos, producer_alternatives(data, sources)),
            sources=sources,
            initial_states=initial_states,
            overrides=NeededFeatureOverrides.collect(data, replacements, needed_combos),
        )

    def apply(self, text: str, combo_id: comboid | None = None) -> str:
        '''Substitutes the replacements of a single text, the ones its aliases stand for included. A
        replacement selecting nothing stays as written, and an inclusion is left untouched: writing one
        needs the other texts of the field it belongs to, which only render_field has.'''
        def replace(match: re.Match[str]) -> str:
            selected = self.replacements.select(match['key'], match['selector'], combo_id)
            return selected[0].resolve(int(match['face']) if match['face'] else None) if selected else match[0]

        return FEATURE_REPLACEMENT_PATTERN.sub(replace, expand_aliases(text))

    def assemble(self, texts: Mapping[SourceIndex, str], merge: MergeTexts, only_when_included: frozenset[SourceIndex] = frozenset()) -> str:
        '''Writes one field of the variant out of the texts its sources wrote for it, resolving the
        inclusions they mention against the same sources.'''
        return FieldAssembly(
            producers=self.producers,
            combo_ids=self.source_combo_ids,
            texts=texts,
            merge=merge,
            only_when_included=only_when_included,
        ).assemble()

    def texts_by_source(self, states: Sequence[SourcedState], field: str) -> dict[SourceIndex, str]:
        '''What the given rows write for one field, with their replacements substituted, grouped by the
        source each row comes from, in row order: two rows of the same source write a single text.'''
        texts = dict[SourceIndex, str]()
        for state in states:
            if text := self.apply(getattr(state.row, field), self.source_combo_ids[state.source]):
                texts[state.source] = join_texts([texts[state.source], text]) if state.source in texts else text
        return texts

    def render_ingredient(self, ingredient: CardInVariant | TemplateInVariant) -> None:
        '''Writes everything an ingredient of the variant inherits from its sources: where it starts,
        whether it must be the commander, which face it is used by, and its starting card states, each
        assembled the way the text fields of the variant are, so that an inclusion written there is
        answered with the state another source asks the same ingredient for. What the needed feature
        rows it replaces ask of it comes first, both for the locations and for the states, and an
        ingredient no source asks anything of falls back to the defaults of its kind.'''
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
            setattr(ingredient, state_field, self.assemble(
                self.texts_by_source(overriding or states, state_field),
                join_texts if overriding else join_with_conjunction,
            ))

    def render_field(self, field: str, merge: MergeTexts = join_texts, only_when_included: frozenset[SourceIndex] = frozenset()) -> str:
        '''Renders one text field of the variant, from what each of its sources wrote for it, in source
        order. A source with nothing to say writes nothing.'''
        return self.assemble(
            {
                index: self.apply(text, combo_id)
                for index, (source, combo_id) in enumerate(zip(self.sources, self.source_combo_ids))
                if (text := getattr(source, field, ''))
            },
            merge,
            only_when_included,
        )
