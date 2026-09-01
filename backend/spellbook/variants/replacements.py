from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Sequence, TypeVar
from .variant_data import Data
from .combo_graph import FeatureWithAttributes
from spellbook.models import Card, Combo, FeatureNeededInCombo, FeatureOfCard, Ingredient, Template
from spellbook.models.references import FEATURE_INCLUSION_PATTERN, FEATURE_REPLACEMENT_PATTERN


_C = TypeVar('_C', bound='Candidate')


@dataclass(frozen=True, kw_only=True)
class Candidate:
    '''What a feature name resolves to in a text, and the names of the attributes the feature was
    produced with, so that it can be selected by attribute.'''
    attributes: frozenset[str] = frozenset()


@dataclass(frozen=True, kw_only=True)
class Replacement(Candidate):
    '''A single rendered replacement for a feature, keeping the backing card (when the replacement
    is a lone card) so that a face override in the text can still resolve to a specific face name.'''
    text: str
    card: Card | None = None

    def resolve(self, face: int | None) -> str:
        if face is not None and self.card is not None and 1 <= face <= self.card.faces:
            return self.card.face_name(face, short=True)
        return self.text


@dataclass(frozen=True, kw_only=True)
class Producer(Candidate):
    '''A single combo or card feature producing a feature, identified by its position among the
    sources of texts of the variant.'''
    index: int


def join_texts(texts: Iterable[str]) -> str:
    '''How the texts of a field are combined into one, both where an inclusion writes them and where
    they are appended to each other.'''
    return '\n'.join(texts)


def merge_used_faces(initial_states: Sequence[Ingredient]) -> int | None:
    '''Merges the used faces of the ingredients contributing a card to a variant: a specified face is
    kept only when every contributor that specifies one agrees on the same number (blanks are ignored).'''
    faces = {getattr(state, 'used_face', None) for state in initial_states}
    faces.discard(None)
    return next(iter(faces)) if len(faces) == 1 else None


def select_candidates(candidates: list[_C], selector: str | None) -> list[_C]:
    '''Picks among the candidates of a feature: a number selects the one in that position, an attribute
    name keeps the ones produced with an attribute of that name, and no selector keeps them all. An
    empty result means the text has nothing to resolve to.'''
    if selector is None:
        return candidates
    if selector.isdigit():
        index = int(selector) - 1
        return [candidates[index]] if 0 <= index < len(candidates) else []
    attribute = selector.casefold()
    return [candidate for candidate in candidates if attribute in candidate.attributes]


class FeatureIndex(Generic[_C]):
    '''What the feature names of a single variant resolve to.

    The same feature can resolve to more than one thing in a variant, so each list is also ordered
    per combo, following the needed feature rows of that combo: this way the positional selector of
    a text always points at the same needed feature row, in every variant.
    '''

    def __init__(self, base: dict[str, list[_C]], by_combo: dict[int, dict[str, list[_C]]]) -> None:
        self.base = base
        self.by_combo = by_combo

    def candidates_for(self, key: str, combo_id: int | None) -> list[_C]:
        if combo_id is not None:
            for_combo = self.by_combo.get(combo_id)
            if for_combo is not None and key in for_combo:
                return for_combo[key]
        return self.base.get(key, [])

    def select(self, key: str, selector: str | None, combo_id: int | None) -> list[_C]:
        return select_candidates(self.candidates_for(key, combo_id), selector)


def order_by_needed_features(
    data: Data,
    needed_combos: Sequence[Combo],
    groups: dict[str, list[tuple[frozenset[int], list[_C]]]],
) -> dict[int, dict[str, list[_C]]]:
    '''Orders the candidates of every feature per combo, following the needed feature rows of that
    combo: the groups a row matches come first, in row order, and the ones no row asks for stay
    reachable after them.'''
    by_combo = dict[int, dict[str, list[_C]]]()
    for combo in needed_combos:
        needed_features_of_combo = defaultdict[int, list[FeatureNeededInCombo]](list)
        for feature_needed in data.combo_to_needed_features[combo.id]:
            needed_features_of_combo[feature_needed.feature_id].append(feature_needed)
        for_combo = dict[str, list[_C]]()
        for feature_id, feature_needed_rows in needed_features_of_combo.items():
            feature_name = data.id_to_feature[feature_id].name
            feature_groups = groups.get(feature_name)
            if feature_groups is None or len(feature_groups) < 2:
                continue
            ordered = list[_C]()
            taken = set[int]()
            for feature_needed in feature_needed_rows:
                matcher = data.feature_needed_in_combo_to_attributes_matcher[feature_needed.id]
                for i, (attributes, candidates) in enumerate(feature_groups):
                    if i not in taken and matcher.matches(attributes):
                        taken.add(i)
                        ordered.extend(candidates)
            ordered.extend(candidate for i, (_, candidates) in enumerate(feature_groups) if i not in taken for candidate in candidates)
            for_combo[feature_name] = ordered
        if for_combo:
            by_combo[combo.id] = for_combo
    return by_combo


def initial_states(
    data: Data,
    needed_combos: Sequence[Combo],
    needed_feature_of_cards: Sequence[FeatureOfCard],
    card_positions: dict[int, int],
    template_positions: dict[int, int],
) -> tuple[dict[int, list[Ingredient]], dict[int, list[Ingredient]]]:
    '''The rows contributing a starting state to each ingredient of the variant, keyed by card and by
    template: the card features first, then the rows of the needed combos, in combo order. Only the
    ingredients the variant ends up with are collected, which is what the positions carry.'''
    cards = defaultdict[int, list[Ingredient]](list)
    templates = defaultdict[int, list[Ingredient]](list)
    for feature_of_card in needed_feature_of_cards:
        cards[feature_of_card.card_id].append(feature_of_card)
    for combo in needed_combos:
        for card_in_combo in data.combo_to_cards[combo.id]:
            if card_in_combo.card_id in card_positions:
                cards[card_in_combo.card_id].append(card_in_combo)
        for template_in_combo in data.combo_to_templates[combo.id]:
            if template_in_combo.template_id in template_positions:
                templates[template_in_combo.template_id].append(template_in_combo)
    return cards, templates


def ingredient_position(
    cards: list[Card],
    templates: list[Template],
    card_positions: dict[int, int],
    template_positions: dict[int, int],
) -> tuple[int, ...]:
    '''Position of a replacement among the ingredients of the variant, used to order the replacements
    of a feature that share the same attributes.'''
    last = len(card_positions) + len(template_positions) + 1
    positions = [card_positions.get(c.id, last) for c in cards]
    positions.extend(len(card_positions) + template_positions.get(t.id, last) for t in templates)
    return tuple(sorted(positions))


def replacements_index(
    data: Data,
    replacements: dict[FeatureWithAttributes, list[tuple[list[Card], list[Template]]]],
    needed_combos: Sequence[Combo],
    used_faces: dict[int, int | None],
    card_positions: dict[int, int],
    template_positions: dict[int, int],
) -> FeatureIndex[Replacement]:
    '''What every feature name is replaced with, from the replacements of the variant. The used_faces
    mapping (card id -> used face) makes a card whose face is specified display the corresponding half
    of its name instead of the whole name.'''
    needed_features_by_feature = defaultdict[int, list[FeatureNeededInCombo]](list)
    for combo in needed_combos:
        for feature_needed in data.combo_to_needed_features[combo.id]:
            needed_features_by_feature[feature_needed.feature_id].append(feature_needed)
    # Replacements of the same feature name, grouped by the attributes they were produced with
    groups = defaultdict[str, list[tuple[frozenset[int], tuple[str, ...], list[Replacement]]]](list)
    for feature, replacement_list in replacements.items():
        corresponding_needed_features = needed_features_by_feature.get(feature.feature.id)
        if corresponding_needed_features and not any(data.feature_needed_in_combo_to_attributes_matcher[corresponding_needed_feature.id].matches(feature.attributes) for corresponding_needed_feature in corresponding_needed_features):
            # if all combos needing that feature don't find a match with attributes the replacement is not applied
            continue
        attribute_names = tuple(sorted(data.id_to_feature_attribute[a].name for a in feature.attributes if a in data.id_to_feature_attribute))
        attributes = frozenset(name.casefold() for name in attribute_names)
        rendered = list[tuple[tuple[int, ...], Replacement]]()
        for cards, templates in replacement_list:
            names = [
                c.face_name(used_faces.get(c.id), short=True)
                for c in cards
            ] + [
                t.name
                for t in templates
            ]
            backing_card = cards[0] if len(cards) == 1 and not templates else None
            rendered.append((
                ingredient_position(cards, templates, card_positions, template_positions),
                Replacement(text=' + '.join(names), card=backing_card, attributes=attributes),
            ))
        rendered.sort(key=lambda entry: entry[0])
        groups[feature.feature.name].append((feature.attributes, attribute_names, [replacement for _, replacement in rendered]))
    base = dict[str, list[Replacement]]()
    for name, entries in groups.items():
        entries.sort(key=lambda entry: entry[1])
        base[name] = [replacement for entry in entries for replacement in entry[2]]
    by_combo = order_by_needed_features(data, needed_combos, {name: [(entry[0], entry[2]) for entry in entries] for name, entries in groups.items()})
    return FeatureIndex(base, by_combo)


def producers_index(
    data: Data,
    needed_combos: Sequence[Combo],
    needed_feature_of_cards: Sequence[FeatureOfCard],
) -> FeatureIndex[Producer]:
    '''Which sources of the variant produce every feature name, grouped by the attributes they produced
    it with the way the replacements of a feature are, so that the same selector picks the same thing
    in both syntaxes.'''
    # the attributes a source produced a feature with, merged when it produces it through more than one row
    produced = defaultdict[str, dict[int, set[int]]](dict)
    for index, combo in enumerate(needed_combos):
        for feature_produced in data.combo_to_produced_features[combo.id]:
            name = data.id_to_feature[feature_produced.feature_id].name
            produced[name].setdefault(index, set()).update(data.feature_produced_in_combo_to_attributes[feature_produced.id])
    for index, feature_of_card in enumerate(needed_feature_of_cards, start=len(needed_combos)):
        name = data.id_to_feature[feature_of_card.feature_id].name
        produced[name].setdefault(index, set()).update(data.feature_of_card_to_attributes[feature_of_card.id])
    base = dict[str, list[Producer]]()
    groups = dict[str, list[tuple[frozenset[int], list[Producer]]]]()
    for name, attributes_by_index in produced.items():
        producers = [
            (
                frozenset(attribute_ids),
                Producer(
                    index=index,
                    attributes=frozenset(data.id_to_feature_attribute[a].name.casefold() for a in attribute_ids if a in data.id_to_feature_attribute),
                ),
            )
            for index, attribute_ids in attributes_by_index.items()
        ]
        base[name] = [producer for _, producer in producers]
        groups[name] = [(attribute_ids, [producer]) for attribute_ids, producer in producers]
    return FeatureIndex(base, order_by_needed_features(data, needed_combos, groups))


class VariantContext:
    '''Renders every text of a single variant, resolving the feature names they mention: [[name]] is
    replaced with what produces the feature, {{name}} with the text those producers wrote in the same
    field.

    The texts of a field come from its sources, the needed combos followed by the needed card features,
    each identified by its position among them. That index space spans every field, so one context is
    built per variant and reused by all of them.

    Aliases registered while rendering one text are visible to every text rendered afterwards, so the
    rendering order matters: the ingredient states first, in the ingredients' display order, then the
    variant text fields.
    '''

    def __init__(
        self,
        replacements: FeatureIndex[Replacement],
        producers: FeatureIndex[Producer],
        needed_combos: Sequence[Combo],
        needed_feature_of_cards: Sequence[FeatureOfCard],
        card_initial_states: dict[int, list[Ingredient]],
        template_initial_states: dict[int, list[Ingredient]],
    ) -> None:
        self.replacements = replacements
        self.producers = producers
        # the rows every ingredient of the variant inherits its starting state from
        self.card_initial_states = card_initial_states
        self.template_initial_states = template_initial_states
        # the sources of every text field, numbered the way producers_index numbered them
        self.sources: Sequence[Combo | FeatureOfCard] = [*needed_combos, *needed_feature_of_cards]
        # the combo a source's placeholders are resolved against, blank for a text coming from a card
        self.source_combo_ids: Sequence[int | None] = [c.id for c in needed_combos] + [None] * len(needed_feature_of_cards)
        self.aliases = dict[str, list[Replacement]]()

    @classmethod
    def build(
        cls,
        data: Data,
        replacements: dict[FeatureWithAttributes, list[tuple[list[Card], list[Template]]]],
        needed_combos: Sequence[Combo],
        needed_feature_of_cards: Sequence[FeatureOfCard],
        card_positions: dict[int, int] = {},
        template_positions: dict[int, int] = {},
    ) -> 'VariantContext':
        '''Builds the context that renders the texts of a variant. Everything it holds is derived from
        the variant's replacements, sources and ingredients, so it is computed once and reused across
        every text it regenerates. The states collected for a card give the face it is used by, which
        makes a card whose face is specified display the corresponding half of its name.'''
        card_initial_states, template_initial_states = initial_states(data, needed_combos, needed_feature_of_cards, card_positions, template_positions)
        used_faces = {card_id: merge_used_faces(states) for card_id, states in card_initial_states.items()}
        return cls(
            replacements=replacements_index(data, replacements, needed_combos, used_faces, card_positions, template_positions),
            producers=producers_index(data, needed_combos, needed_feature_of_cards),
            needed_combos=needed_combos,
            needed_feature_of_cards=needed_feature_of_cards,
            card_initial_states=card_initial_states,
            template_initial_states=template_initial_states,
        )

    def apply(self, text: str, combo_id: int | None = None) -> str:
        '''Substitutes the replacements of a single text. An inclusion is left alone: it needs the
        other texts of the field it belongs to, which only render_field has.'''
        def replacement_with_fallback(key: str, face: str | None, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
            face_index = int(face) if face else None
            candidates = self.aliases[key] if key in self.aliases else self.replacements.candidates_for(key, combo_id)
            strings = select_candidates(candidates, selector)
            if not strings:
                return otherwise
            result = strings[0].resolve(face_index)
            if alias:
                # when a face is selected, the alias saves the resolved face name; otherwise it aliases the whole feature
                self.aliases[alias] = [Replacement(text=result)] if face_index is not None else candidates
            if postfix_alias:
                self.aliases.setdefault(postfix_alias, []).append(Replacement(text=result))
            return result

        return FEATURE_REPLACEMENT_PATTERN.sub(
            lambda m: replacement_with_fallback(m.group('key'), m.group('face'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
            text,
        )

    def render_ingredient_states(
        self,
        ingredient: Ingredient,
        features_for_override: Sequence[FeatureNeededInCombo],
    ) -> None:
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

    def render_field(self, field: str, merge: Callable[[Iterable[str]], str] = join_texts) -> str:
        '''Renders one text field of the variant, from what each of its sources wrote for it, in source
        order. An inclusion is replaced with the texts of the sources it selects, which are then left
        out of the result, because they have already been written where they were mentioned. Deciding
        that is what a whole field is needed for: a field holding no inclusion is every text of it,
        combined. A source with nothing to say writes nothing, and a card feature has only the fields
        it shares with a combo.'''
        by_source = dict[int, str]()
        for index, source in enumerate(self.sources):
            text = getattr(source, field, '')
            if text:
                by_source[index] = self.apply(text, self.source_combo_ids[index])

        def selected_by(index: int, key: str, selector: str | None) -> list[Producer]:
            # a text never writes itself, so the sole producer of a feature mentioning it has nothing to write
            return [producer for producer in self.producers.select(key, selector, self.source_combo_ids[index]) if producer.index != index]

        consumed = set[int]()
        for index, text in by_source.items():
            for match in FEATURE_INCLUSION_PATTERN.finditer(text):
                consumed.update(producer.index for producer in selected_by(index, match.group('key'), match.group('selector')))

        def expand(index: int, ancestors: frozenset[int]) -> str:
            def inclusion_with_fallback(key: str, selector: str | None, otherwise: str) -> str:
                producers = selected_by(index, key, selector)
                if not producers:
                    return otherwise
                # a source already being written above is skipped, so that a cycle of inclusions terminates
                written = ancestors | {index}
                parts = (expand(producer.index, written) for producer in producers if producer.index not in written)
                return merge(part for part in parts if part)
            return FEATURE_INCLUSION_PATTERN.sub(
                lambda m: inclusion_with_fallback(m.group('key'), m.group('selector'), m.group(0)),
                by_source.get(index, ''),
            )

        expanded = (expand(index, frozenset()) for index in by_source if index not in consumed)
        return merge(text for text in expanded if text)
