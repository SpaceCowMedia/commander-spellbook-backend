import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Generic, Iterable, Mapping, Sequence, TypeVar
from .variant_data import Data
from .combo_graph import FeatureWithAttributes, cardid, comboid, featureid, templateid
from spellbook.models import Card, Combo, FeatureNeededInCombo, FeatureOfCard, Ingredient, Template
from spellbook.models.references import FEATURE_INCLUSION_PATTERN, FEATURE_REPLACEMENT_PATTERN


FeatureName = str
# Position of a source among the ones a variant takes its texts from
SourceIndex = int
# A text of a variant is written either by a combo it needs or by a feature of one of its cards
TextSource = Combo | FeatureOfCard
# How the several texts of one field are combined into the single text of the variant
MergeTexts = Callable[[Iterable[str]], str]
Recipe = tuple[list[Card], list[Template]]

_C = TypeVar('_C')


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
    all. Nothing selected means the text has nothing to resolve to, and stays as it was written.'''
    if selector is None:
        return candidates_of(alternatives)
    if not selector.isdigit():
        return candidates_of(alternative for alternative in alternatives if alternative.has_attribute(selector))
    position = int(selector) - 1
    candidates = candidates_of(alternatives)
    return candidates[position:position + 1] if position >= 0 else []


def already_resolved(text: str) -> Alternative[Replacement]:
    '''A name a text already resolved, saved under an alias for the texts rendered after it.'''
    return Alternative(candidates=(Replacement(text=text),))


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

@dataclass(frozen=True)
class IngredientPositions:
    '''Where each ingredient of the variant is displayed. This orders the ways of producing the same
    feature, so that a text names them the way the reader sees them listed.'''
    cards: Mapping[cardid, int] = field(default_factory=dict)
    templates: Mapping[templateid, int] = field(default_factory=dict)

    def position_of(self, cards: Iterable[Card], templates: Iterable[Template]) -> tuple[int, ...]:
        last = len(self.cards) + len(self.templates) + 1
        positions = [self.cards.get(c.id, last) for c in cards]
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


def replacement_of(recipe: Recipe, used_faces: Mapping[cardid, int | None]) -> Replacement:
    '''The name a text shows for one way of producing a feature. A card used by one of its faces shows
    that half of its name, and a lone card is kept, so that a face override in the text still resolves.'''
    cards, templates = recipe
    names = [c.face_name(used_faces.get(c.id), short=True) for c in cards] + [t.name for t in templates]
    return Replacement(
        text=' + '.join(names),
        card=cards[0] if len(cards) == 1 and not templates else None,
    )


def replacement_alternatives(
    data: Data,
    replacements: Mapping[FeatureWithAttributes, Sequence[Recipe]],
    needed_combos: Sequence[Combo],
    used_faces: Mapping[cardid, int | None],
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
                replacement_of(recipe, used_faces)
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


@dataclass(frozen=True)
class InitialStates:
    '''The rows every ingredient of a variant inherits its starting state from.'''
    cards: Mapping[cardid, Sequence[Ingredient]]
    templates: Mapping[templateid, Sequence[Ingredient]]

    @classmethod
    def collect(cls, data: Data, sources: Sequence[TextSource], positions: IngredientPositions) -> 'InitialStates':
        '''The card features first, then the rows of the needed combos, in combo order. Only the
        ingredients the variant ends up with are collected, which is what the positions carry.'''
        cards = defaultdict[cardid, list[Ingredient]](list)
        templates = defaultdict[templateid, list[Ingredient]](list)
        for source in sources:
            if isinstance(source, FeatureOfCard):
                cards[source.card_id].append(source)
        for source in sources:
            if not isinstance(source, Combo):
                continue
            for card_in_combo in data.combo_to_cards[source.id]:
                if card_in_combo.card_id in positions.cards:
                    cards[card_in_combo.card_id].append(card_in_combo)
            for template_in_combo in data.combo_to_templates[source.id]:
                if template_in_combo.template_id in positions.templates:
                    templates[template_in_combo.template_id].append(template_in_combo)
        return cls(cards=cards, templates=templates)

    def used_faces(self) -> dict[cardid, int | None]:
        return {card_id: merge_used_faces(states) for card_id, states in self.cards.items()}


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


@dataclass(frozen=True)
class FieldAssembly:
    '''Assembles one text field of a variant, out of the texts its sources wrote for it.

    An inclusion is replaced with the texts of the sources it names, which are then left out of the
    result, because they have already been written where they were mentioned. Deciding that is why a
    whole field is assembled at once: a field holding no inclusion is simply every text of it, merged.
    '''
    producers: FeatureIndex[SourceIndex]
    combo_ids: Sequence[comboid | None]
    texts: Mapping[SourceIndex, str]
    merge: MergeTexts

    def assemble(self) -> str:
        included = self.included_sources()
        written = (self.write(source, frozenset()) for source in self.texts if source not in included)
        return self.merge(text for text in written if text)

    def named_by(self, source: SourceIndex, inclusion: re.Match[str]) -> Sequence[SourceIndex]:
        '''The sources an inclusion names, never the one writing it: a text does not write itself, so
        the sole producer of a feature its own text mentions has nothing to write there.'''
        named = self.producers.select(inclusion['key'], inclusion['selector'], self.combo_ids[source])
        return [other for other in named if other != source]

    def included_sources(self) -> set[SourceIndex]:
        '''Every source named by an inclusion anywhere in the field, which is what keeps its text from
        being appended on its own.'''
        return {
            other
            for source, text in self.texts.items()
            for inclusion in FEATURE_INCLUSION_PATTERN.finditer(text)
            for other in self.named_by(source, inclusion)
        }

    def write(self, source: SourceIndex, ancestors: frozenset[SourceIndex]) -> str:
        '''The text of one source, with its inclusions written out in place. A source already being
        written higher up is skipped, so that a cycle of inclusions terminates.'''
        written = ancestors | {source}

        def include(inclusion: re.Match[str]) -> str:
            named = self.named_by(source, inclusion)
            if not named:
                return inclusion[0]
            texts = (self.write(other, written) for other in named if other not in written)
            return self.merge(text for text in texts if text)

        return FEATURE_INCLUSION_PATTERN.sub(include, self.texts.get(source, ''))


class VariantContext:
    '''Renders every text of a single variant, resolving the feature names they mention.

    The texts come from the sources of the variant, the combos it needs followed by the features of its
    cards, each identified by its position among them. That numbering spans every field, so one context
    is built per variant and reused by all of them, along with everything else derived from the same
    sources: what replaces a feature name, which sources produce it, and the starting states of the
    ingredients.

    An alias registered while rendering one text is visible to every text rendered afterwards, so the
    rendering order matters: the ingredient states first, in the ingredients' display order, then the
    text fields of the variant.
    '''

    def __init__(
        self,
        replacements: FeatureIndex[Replacement],
        producers: FeatureIndex[SourceIndex],
        sources: Sequence[TextSource],
        initial_states: InitialStates,
    ) -> None:
        self.replacements = replacements
        self.producers = producers
        self.sources = sources
        self.initial_states = initial_states
        self.source_combo_ids = [owning_combo_id(source) for source in sources]
        self.aliases = dict[str, Sequence[Alternative[Replacement]]]()

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
        sources: list[TextSource] = [*needed_combos, *needed_feature_of_cards]
        initial_states = InitialStates.collect(data, sources, positions)
        return cls(
            replacements=index_of(data, needed_combos, replacement_alternatives(
                data, replacements, needed_combos, initial_states.used_faces(), positions,
            )),
            producers=index_of(data, needed_combos, producer_alternatives(data, sources)),
            sources=sources,
            initial_states=initial_states,
        )

    def apply(self, text: str, combo_id: comboid | None = None) -> str:
        '''Substitutes the replacements of a single text. An inclusion is left untouched: writing one
        needs the other texts of the field it belongs to, which only render_field has.'''
        def replace(match: re.Match[str]) -> str:
            key = match['key']
            alternatives = self.aliases[key] if key in self.aliases else self.replacements.alternatives(key, combo_id)
            selected = select(alternatives, match['selector'])
            if not selected:
                return match[0]
            face = int(match['face']) if match['face'] else None
            name = selected[0].resolve(face)
            if alias := match['alias']:
                # a face selection aliases the half of the name it resolved, anything else the whole feature
                self.aliases[alias] = (already_resolved(name),) if face is not None else alternatives
            if postfix_alias := match['postfix_alias']:
                self.aliases[postfix_alias] = (*self.aliases.get(postfix_alias, ()), already_resolved(name))
            return name

        return FEATURE_REPLACEMENT_PATTERN.sub(replace, text)

    def render_ingredient_states(self, ingredient: Ingredient, features_for_override: Iterable[FeatureNeededInCombo]) -> None:
        '''Substitutes the placeholders in the starting card state fields of an ingredient, preferring the
        states of the needed features it replaces over the ones inherited from the combos it appears in.'''
        for location, state in Ingredient.CARD_STATE_FIELDS.items():
            if location not in ingredient.zone_locations:
                setattr(ingredient, state, '')
                continue
            overrides = [
                self.apply(getattr(feature, state), feature.combo_id)
                for feature in features_for_override
                if location in feature.zone_locations and getattr(feature, state)
            ]
            setattr(ingredient, state, join_texts(overrides) if overrides else self.apply(getattr(ingredient, state)))

    def render_field(self, field: str, merge: MergeTexts = join_texts) -> str:
        '''Renders one text field of the variant, from what each of its sources wrote for it, in source
        order. A source with nothing to say writes nothing, and a feature of a card has only the fields
        it shares with a combo.'''
        return FieldAssembly(
            producers=self.producers,
            combo_ids=self.source_combo_ids,
            texts={
                index: self.apply(text, combo_id)
                for index, (source, combo_id) in enumerate(zip(self.sources, self.source_combo_ids))
                if (text := getattr(source, field, ''))
            },
            merge=merge,
        ).assemble()
