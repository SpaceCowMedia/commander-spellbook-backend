import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence
from .variant_data import Data
from .combo_graph import FeatureWithAttributes
from spellbook.models import Card, Combo, FeatureNeededInCombo, Ingredient, Template


# A feature replacement looks like [[key#face|alias$selector|postfix_alias]], where every part but the key is optional:
# - #face selects which face of a multi-faced card to display (a symbol that cannot appear in a card name);
# - |alias saves the replacement under an alias for later reuse;
# - $selector picks one among the multiple replacements of the same feature, either by position
#   (the position of the needed feature row of the combo the text belongs to) or by attribute name;
# - |postfix_alias saves the selected replacement under an alias.
FEATURE_REPLACEMENT_PATTERN = re.compile(r'\[\[(?P<key>.+?)(?:#(?P<face>[1-9]\d*))?(?:\|(?P<alias>[^$|]+?))?(?:\$(?P<selector>[^$|\]]+)(?:\|(?P<postfix_alias>[^$|]+?))?)?\]\]', re.IGNORECASE)


def format_feature_replacement(key: str, face: str | None, alias: str | None, selector: str | None, postfix_alias: str | None) -> str:
    '''Rebuilds a feature replacement from its parts, the inverse of FEATURE_REPLACEMENT_PATTERN.'''
    result = key
    if face is not None:
        result += f'#{face}'
    if alias is not None:
        result += f'|{alias}'
    if selector is not None:
        result += f'${selector}'
        if postfix_alias is not None:
            result += f'|{postfix_alias}'
    return f'[[{result}]]'


@dataclass(frozen=True)
class Replacement:
    '''A single rendered replacement for a feature, keeping the backing card (when the replacement
    is a lone card) so that a face override in the text can still resolve to a specific face name,
    and the names of the attributes it was produced with, so that it can be selected by attribute.'''
    text: str
    card: Card | None = None
    attributes: frozenset[str] = frozenset()

    def resolve(self, face: int | None) -> str:
        if face is not None and self.card is not None and 1 <= face <= self.card.faces:
            return self.card.face_name(face, short=True)
        return self.text


class ReplacementContext:
    '''Substitutes the placeholders of every text of a single variant, from the replacements available
    to it, keyed by feature name.

    The same feature can be replaced by more than one thing in a variant, so each list is also ordered
    per combo, following the needed feature rows of that combo: this way the positional selector of
    [[feature$1]] always points at the same needed feature row, in every variant.

    Aliases registered while rendering one text are visible to every text rendered afterwards, so one
    context spans a whole variant and the rendering order matters: the ingredient states first, in the
    ingredients' display order, then the variant text fields.
    '''

    def __init__(self, base: dict[str, list[Replacement]], by_combo: dict[int, dict[str, list[Replacement]]]) -> None:
        self.base = base
        self.by_combo = by_combo
        self.aliases = dict[str, list[Replacement]]()

    @classmethod
    def build(
        cls,
        data: Data,
        replacements: dict[FeatureWithAttributes, list[tuple[list[Card], list[Template]]]],
        needed_combos: Sequence[Combo],
        used_faces: dict[int, int | None],
        card_positions: dict[int, int] = {},
        template_positions: dict[int, int] = {},
    ) -> 'ReplacementContext':
        '''
        Builds the context that renders the texts of a variant, from its replacements keyed by feature name.
        This depends only on the variant's replacements and needed combos, so it is
        computed once and reused across every text field the variant regenerates.
        The used_faces mapping (card id -> used face) makes a card whose face is specified
        display the corresponding half of its name instead of the whole name.
        '''
        needed_features_by_feature = defaultdict[int, list[FeatureNeededInCombo]](list)
        for combo in needed_combos:
            for feature_needed in data.combo_to_needed_features[combo.id]:
                needed_features_by_feature[feature_needed.feature_id].append(feature_needed)
        # Replacements of the same feature name, grouped by the attributes they were produced with
        groups = defaultdict[str, list[tuple[FeatureWithAttributes, tuple[str, ...], list[Replacement]]]](list)
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
                    cls._position(cards, templates, card_positions, template_positions),
                    Replacement(text=' + '.join(names), card=backing_card, attributes=attributes),
                ))
            rendered.sort(key=lambda entry: entry[0])
            groups[feature.feature.name].append((feature, attribute_names, [replacement for _, replacement in rendered]))
        base = dict[str, list[Replacement]]()
        for name, entries in groups.items():
            entries.sort(key=lambda entry: entry[1])
            base[name] = [replacement for entry in entries for replacement in entry[2]]
        by_combo = dict[int, dict[str, list[Replacement]]]()
        for combo in needed_combos:
            needed_features_of_combo = defaultdict[int, list[FeatureNeededInCombo]](list)
            for feature_needed in data.combo_to_needed_features[combo.id]:
                needed_features_of_combo[feature_needed.feature_id].append(feature_needed)
            for_combo = dict[str, list[Replacement]]()
            for feature_id, feature_needed_rows in needed_features_of_combo.items():
                feature_name = data.id_to_feature[feature_id].name
                feature_groups = groups.get(feature_name)
                if feature_groups is None or len(feature_groups) < 2:
                    continue
                ordered = list[Replacement]()
                taken = set[int]()
                for feature_needed in feature_needed_rows:
                    matcher = data.feature_needed_in_combo_to_attributes_matcher[feature_needed.id]
                    for i, entry in enumerate(feature_groups):
                        if i not in taken and matcher.matches(entry[0].attributes):
                            taken.add(i)
                            ordered.extend(entry[2])
                ordered.extend(replacement for i, entry in enumerate(feature_groups) if i not in taken for replacement in entry[2])
                for_combo[feature_name] = ordered
            if for_combo:
                by_combo[combo.id] = for_combo
        return cls(base, by_combo)

    @staticmethod
    def _position(
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

    def _replacements_for(self, key: str, combo_id: int | None) -> list[Replacement]:
        if combo_id is not None:
            for_combo = self.by_combo.get(combo_id)
            if for_combo is not None and key in for_combo:
                return for_combo[key]
        return self.base.get(key, [])

    @staticmethod
    def _select(strings: list[Replacement], selector: str | None) -> Replacement | None:
        '''Picks one among the replacements of a feature: a number selects by position, anything else
        selects the first replacement produced with an attribute of that name.'''
        if selector is None:
            return strings[0] if strings else None
        if selector.isdigit():
            index = int(selector) - 1
            return strings[index] if 0 <= index < len(strings) else None
        attribute = selector.casefold()
        return next((replacement for replacement in strings if attribute in replacement.attributes), None)

    def apply(self, text: str, combo_id: int | None = None) -> str:
        def replacement_with_fallback(key: str, face: str | None, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
            face_index = int(face) if face else None
            strings = self.aliases[key] if key in self.aliases else self._replacements_for(key, combo_id)
            replacement = self._select(strings, selector)
            if replacement is None:
                return otherwise
            result = replacement.resolve(face_index)
            if alias:
                # when a face is selected, the alias saves the resolved face name; otherwise it aliases the whole feature
                self.aliases[alias] = [Replacement(text=result)] if face_index is not None else strings
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
            setattr(ingredient, state, '\n'.join(overrides) if overrides else self.apply(getattr(ingredient, state)))
