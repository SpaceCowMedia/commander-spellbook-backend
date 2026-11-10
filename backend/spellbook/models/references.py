import re
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Collection, Iterable, Iterator, Literal, Mapping, Sequence, TypeVar
from django.db.models import Manager, Q
from .utils import DEFAULT_BATCH_SIZE
if TYPE_CHECKING:
    from .combo import Combo
    from .explanation import Explanation
    from .feature import Feature
    from .feature_attribute import AttributeValue, FeatureAttribute
    from .ingredient import Ingredient
    TextModel = type[Combo] | type[Ingredient] | type[Explanation] | type[AttributeValue]


_T = TypeVar('_T')

# The characters of the reference syntax, each defined once: every pattern, formatter, validator and
# help text is built from them. Migrations keep a copy of the syntax of their time instead.
ALIAS_PREFIX = '!'
LINE_REFERENCE_PREFIX = '#'
REFERENCE_PREFIXES = (ALIAS_PREFIX, LINE_REFERENCE_PREFIX)
REFERENCE_BRACKETS = ('[[', ']]')
FACE_MARKER = '#'
SELECTOR_MARKER = '$'
KEY_MARKER = '@'
ALIAS_MARKER = '|'
BRACKET_CHARACTERS = ('[', ']')
# the characters every part of a reference is delimited by, which a feature name or an alias
# cannot hold anywhere
FEATURE_NAME_RESERVED_CHARACTERS = tuple(dict.fromkeys((*REFERENCE_PREFIXES, FACE_MARKER, SELECTOR_MARKER, KEY_MARKER, ALIAS_MARKER, *BRACKET_CHARACTERS)))
# an attribute name is written after the selector marker, up to the key or the alias, and after the
# key marker, being a key too
ATTRIBUTE_NAME_RESERVED_CHARACTERS = (SELECTOR_MARKER, KEY_MARKER, ALIAS_MARKER, *BRACKET_CHARACTERS)
# the characters no name can hold, since they end the feature of a reference
RESERVED_CHARACTERS = (SELECTOR_MARKER, ALIAS_MARKER)

# What a reference without a key writes, and the keys every producer provides from its own fields: the
# texts of a variant, and the starting states of a card, which only a starting state can reference
DEFAULT_KEY = 'name'
TEXT_KEYS = ('mana_needed', 'easy_prerequisites', 'notable_prerequisites', 'description', 'notes', 'comment')
CARD_STATE_KEYS = ('battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state')
# every other key is a feature attribute, which no attribute can be named after
BUILT_IN_KEYS = (DEFAULT_KEY, *TEXT_KEYS, *CARD_STATE_KEYS)


def escaped(*parts: str) -> str:
    return ''.join(map(re.escape, parts))


def character_class(*excluded: str) -> str:
    '''The regex class of the characters a part of a reference can hold: none of the excluded ones, on a single line.'''
    return f'[^{escaped(*sorted(set("".join(excluded))))}\\n]'


def bracketed(content: str) -> str:
    return f'{REFERENCE_BRACKETS[0]}{content}{REFERENCE_BRACKETS[1]}'


def optional(marker: str, part: str | None) -> str:
    return '' if part is None else f'{marker}{part}'


def between(brackets: tuple[str, str]) -> str:
    '''The regex of whatever a text holds between the given brackets, unless they are part of a longer
    run of the same brackets, which is plain text.'''
    run = re.escape(brackets[0][0])
    return f'(?<!{run}){re.escape(brackets[0])}(?!{run}).*?{re.escape(brackets[1])}'


FEATURE_NAME_CHARACTER = character_class(*FEATURE_NAME_RESERVED_CHARACTERS)
ATTRIBUTE_NAME_CHARACTER = character_class(*ATTRIBUTE_NAME_RESERVED_CHARACTERS)
FEATURE_NAME_RESERVED_CHARACTERS_REGEX = '|'.join(map(re.escape, FEATURE_NAME_RESERVED_CHARACTERS))
ATTRIBUTE_NAME_RESERVED_CHARACTERS_REGEX = '|'.join(map(re.escape, ATTRIBUTE_NAME_RESERVED_CHARACTERS))
RESERVED_CHARACTERS_REGEX = '|'.join(map(re.escape, RESERVED_CHARACTERS))
OPENING = re.escape(REFERENCE_BRACKETS[0])
CLOSING = re.escape(REFERENCE_BRACKETS[1])
KEY_PART = f'(?:{re.escape(KEY_MARKER)}(?P<key>{ATTRIBUTE_NAME_CHARACTER}+))?'

# A feature reference looks like [[feature#face$selector@key|alias]], where every part but the feature is optional:
# - #face selects which face of a multi-faced card to display;
# - $selector picks one among the multiple producers of the same feature, either by position
#   (counting through the copies the combo the text belongs to needs, row after row) or by attribute name;
# - @key picks what of the producers to write, their names by default;
# - |alias names the reference, so that the rest of the text can repeat it as [[!alias]].
FEATURE_REFERENCE_PATTERN = re.compile(
    f'{OPENING}'
    f'(?P<feature>{FEATURE_NAME_CHARACTER}+)'
    f'(?:{re.escape(FACE_MARKER)}(?P<face>[1-9]\\d*))?'
    f'(?:{re.escape(SELECTOR_MARKER)}(?P<selector>{ATTRIBUTE_NAME_CHARACTER}+))?'
    f'{KEY_PART}'
    f'(?:{re.escape(ALIAS_MARKER)}(?P<alias>{FEATURE_NAME_CHARACTER}+))?'
    f'{CLOSING}'
)

# [[!alias]] repeats the reference defining the alias, and [[!alias@key]] repeats it with another key
ALIAS_REFERENCE_PATTERN = re.compile(f'{OPENING}{re.escape(ALIAS_PREFIX)}(?P<alias>{FEATURE_NAME_CHARACTER}+){KEY_PART}{CLOSING}')

# [[#Z]] points at the Zth line of its text, [[#+X]] at the line X lines below, [[#-Y]] at the one Y lines above
LINE_REFERENCE_PATTERN = re.compile(f'{OPENING}{re.escape(LINE_REFERENCE_PREFIX)}(?P<sign>[+-]?)(?P<number>\\d+){CLOSING}')

# whatever a text holds between double brackets, which has to be one of the references above
REFERENCE_PATTERN = re.compile(between(REFERENCE_BRACKETS))


def format_feature_reference(feature: str, face: str | None = None, selector: str | None = None, key: str | None = None, alias: str | None = None) -> str:
    '''Writes a feature reference from its parts, the inverse of FEATURE_REFERENCE_PATTERN.'''
    return bracketed(feature + optional(FACE_MARKER, face) + optional(SELECTOR_MARKER, selector) + optional(KEY_MARKER, key) + optional(ALIAS_MARKER, alias))


def format_alias_reference(alias: str, key: str | None = None) -> str:
    return bracketed(ALIAS_PREFIX + alias + optional(KEY_MARKER, key))


def format_line_reference(number: int | str, sign: str = '') -> str:
    return bracketed(f'{LINE_REFERENCE_PREFIX}{sign}{number}')


def key_of(reference: re.Match[str]) -> str:
    return reference['key'] or DEFAULT_KEY


def referenced_line(reference: re.Match[str], line: int) -> int:
    '''The line of its text a line reference written on the given line points at.'''
    number = int(reference['number'])
    match reference['sign']:
        case '+':
            return line + number
        case '-':
            return line - number
        case _:
            return number


def expand_aliases(text: str) -> str:
    '''Writes every alias a text uses as the reference defining it, with the key the use asks for if
    any, so that whatever reads the result only meets feature names. An alias is known to the whole text
    defining it, before its definition too, and one the text does not define is left as written.'''
    definitions = dict[str, re.Match[str]]()
    for match in FEATURE_REFERENCE_PATTERN.finditer(text):
        if match['alias']:
            definitions.setdefault(match['alias'], match)

    def expand(use: re.Match[str]) -> str:
        definition = definitions.get(use['alias'])
        if definition is None:
            return use[0]
        return format_feature_reference(definition['feature'], definition['face'], definition['selector'], use['key'] or definition['key'])

    return ALIAS_REFERENCE_PATTERN.sub(expand, text) if definitions else text


def feature_references(texts: Iterable[str]) -> Iterator[re.Match[str]]:
    '''The feature references in the texts. An alias use is none of them, since the reference defining
    it stands for it.'''
    for text in texts:
        yield from FEATURE_REFERENCE_PATTERN.finditer(text)


def references_to_features_not_needed(texts: Iterable[str], needed_feature_names: Collection[str]) -> list[str]:
    '''The feature references in the texts of a combo whose feature is not one the combo needs, each
    once, sorted. Names are matched exactly, the way the texts of a variant resolve them.'''
    return sorted({match[0] for match in feature_references(texts) if match['feature'] not in needed_feature_names})


def references_past_copies_needed(texts: Iterable[str], copies_needed: Mapping[str, int]) -> list[str]:
    '''The feature references in the texts of a combo whose position selects none of the copies the
    combo needs of that feature, each once, sorted. A reference to a feature the combo does not need is
    left to references_to_features_not_needed.'''
    return sorted({
        match[0]
        for match in feature_references(texts)
        if match['feature'] in copies_needed and (selector := match['selector']) is not None and selector.isdigit() and not 1 <= int(selector) <= copies_needed[match['feature']]
    })


def attribute_keys_referenced(texts: Iterable[str]) -> set[str]:
    '''The keys the references of the texts write that are no built-in key, their aliases expanded.'''
    return {match['key'] for match in feature_references(map(expand_aliases, texts)) if match['key'] is not None and match['key'] not in BUILT_IN_KEYS}


def references_to_unknown_keys(texts: Iterable[str], attribute_names: Collection[str]) -> list[str]:
    '''The references in the texts to a key that is neither built in nor one of the given attributes,
    each once, sorted, their aliases expanded: every key a producer provides is one or the other.'''
    return sorted({
        match[0]
        for match in feature_references(map(expand_aliases, texts))
        if match['key'] is not None and match['key'] not in BUILT_IN_KEYS and match['key'] not in attribute_names
    })


# A feature is named by the feature of a reference, an attribute by its selector or its key
ReferencePart = Literal['feature', 'selector', 'key']
ATTRIBUTE_PARTS: tuple[ReferencePart, ...] = ('selector', 'key')


def refers_to(reference: re.Match[str], part: ReferencePart, name: str) -> bool:
    '''Whether the part of a reference names the given name, ignoring case the way names are unique. A
    numeric selector is a position, never an attribute.'''
    value = reference[part]
    return value is not None and value.lower() == name.lower() and not (part == 'selector' and value.isdigit())


def ingredient_models() -> tuple['TextModel', ...]:
    '''The models besides combos whose rows hold texts with references: the rows of combos, the
    features of cards, and the texts producers give their attributes.'''
    from .card import FeatureOfCard, FeatureOfCardAttribute
    from .combo import CardInCombo, FeatureNeededInCombo, FeatureProducedInCombo, FeatureProducedInComboAttribute, TemplateInCombo
    return CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, FeatureOfCardAttribute, FeatureProducedInComboAttribute


def references_filter(model: 'TextModel', part: ReferencePart, name: str) -> Q:
    '''Matches the rows of the given model whose texts could reference the given name as the given part
    of a reference, so that a rename only loads the rows that mention it.'''
    start = {'feature': REFERENCE_BRACKETS[0], 'selector': SELECTOR_MARKER, 'key': KEY_MARKER}[part] + name
    query = Q()
    for field in model.text_fields_with_references():
        query |= Q(**{f'{field}__icontains': start})
    return query


def rename_references(text: str, part: ReferencePart, old_name: str, new_name: str) -> str:
    '''Renames a feature or an attribute in the references of a text, the uses of an alias asking for
    the attribute as their key included. Names are matched ignoring case, the way they are unique, and a
    numeric selector is a position, never an attribute.'''
    def rename(match: re.Match[str]) -> str:
        return format_feature_reference(**(match.groupdict() | {part: new_name})) if refers_to(match, part, old_name) else match[0]

    def rename_alias(match: re.Match[str]) -> str:
        return format_alias_reference(match['alias'], new_name) if refers_to(match, 'key', old_name) else match[0]

    text = FEATURE_REFERENCE_PATTERN.sub(rename, text)
    return ALIAS_REFERENCE_PATTERN.sub(rename_alias, text) if part == 'key' else text


def remove_references(text: str, name: str) -> str:
    '''Removes from a text the references selecting an attribute or writing it as a key, the uses of
    their aliases included, which have nothing left to write once the attribute is gone. An alias whose
    definition goes while a use of it writes another key is defined by the first such use instead.'''
    definitions = dict[str, re.Match[str]]()
    for match in FEATURE_REFERENCE_PATTERN.finditer(text):
        if match['alias']:
            definitions.setdefault(match['alias'], match)
    redefined = set[str]()

    def remove_use(use: re.Match[str]) -> str:
        definition = definitions.get(use['alias'])
        if definition is None:
            return use[0]
        if refers_to(definition, 'selector', name) or refers_to(use if use['key'] else definition, 'key', name):
            return ''
        if refers_to(definition, 'key', name) and use['alias'] not in redefined:
            redefined.add(use['alias'])
            return format_feature_reference(definition['feature'], definition['face'], definition['selector'], use['key'], use['alias'])
        return use[0]

    def remove(reference: re.Match[str]) -> str:
        return '' if any(refers_to(reference, part, name) for part in ATTRIBUTE_PARTS) else reference[0]

    return FEATURE_REFERENCE_PATTERN.sub(remove, ALIAS_REFERENCE_PATTERN.sub(remove_use, text))


def replace_in_text_fields(objects: Iterable[_T], fields: Sequence[str], replacement: Callable[[str], str]) -> list[_T]:
    '''Applies the replacement to the given text fields, returning only the objects that changed.'''
    changed = []
    for obj in objects:
        modified = False
        for field in fields:
            old_value = getattr(obj, field)
            new_value = replacement(old_value)
            if new_value != old_value:
                setattr(obj, field, new_value)
                modified = True
        if modified:
            changed.append(obj)
    return changed


def rewrite_rows(model: 'TextModel', rewrite: Callable[[str], str], rows_filter: Q) -> None:
    '''Rewrites the texts of the rows of the model matching the filter, saving only the rows that
    changed. Every row loaded is rewritten, so the order they come in is irrelevant.'''
    fields = model.text_fields_with_references()
    manager: Manager[Any] = model._default_manager
    rows = manager.filter(rows_filter).order_by().only(*fields)
    manager.bulk_update(replace_in_text_fields(rows, fields, rewrite), fields, batch_size=DEFAULT_BATCH_SIZE)


def rename_in_models(models: Iterable['TextModel'], part: ReferencePart, old_name: str, new_name: str) -> Callable[[str], str]:
    '''Renames a feature or an attribute in the texts of the given models that mention it, and returns
    the rename for the texts left to the caller.'''
    rename = partial(rename_references, part=part, old_name=old_name, new_name=new_name)
    for model in models:
        rewrite_rows(model, rename, references_filter(model, part, old_name))
    return rename


def replace_feature_references(instance: Feature, old_name: str):
    '''Propagates the loss of a feature name, by a rename or by a merge into another feature, to
    everything referencing it in a text or displaying it in a recipe.'''
    if old_name and old_name != instance.name:
        replace_feature_references_in_combos(instance, old_name)
        replace_feature_references_in_variants(instance, old_name)


def replace_feature_references_in_combos(instance: Feature, old_name: str):
    from .combo import Combo
    rename = rename_in_models(ingredient_models(), 'feature', old_name, instance.name)
    combo_text_fields = Combo.text_fields_with_references()
    combo_recipe_fields = Combo.recipe_fields()
    combos = list(Combo.rename_prefetched.filter(
        Q(needs=instance, name__contains=old_name) | Q(produces=instance, name__contains=old_name) | Q(removes=instance, name__contains=old_name) | references_filter(Combo, 'feature', old_name),
    ).order_by().distinct().only(*combo_text_fields, *combo_recipe_fields))
    # the two groups barely overlap, so writing each one only the columns it changed keeps the
    # updates from carrying the columns the other group needs
    combos_with_changed_text = replace_in_text_fields(combos, combo_text_fields, rename)
    combos_with_changed_recipe = [combo for combo in combos if combo.update_recipe_from_data()]
    Combo.objects.bulk_update(combos_with_changed_text, combo_text_fields, batch_size=DEFAULT_BATCH_SIZE)
    Combo.objects.bulk_update(combos_with_changed_recipe, combo_recipe_fields, batch_size=DEFAULT_BATCH_SIZE)


def replace_feature_references_in_variants(instance: Feature, old_name: str):
    '''Recomputes the names of the variants producing the feature, the only part of a variant a
    feature name can reach: variants hold no text of their own to reference it from.'''
    from .variant import Variant
    # the ids are taken upfront because the update itself makes the rows stop matching that condition,
    # unordered because rewriting them all makes the order they come in irrelevant
    variant_ids = list(Variant.objects.filter(produces=instance, name__contains=old_name).order_by().values_list('pk', flat=True))
    # only the name is loaded and written, so pre_save is skipped to keep the other fields deferred
    for i in range(0, len(variant_ids), DEFAULT_BATCH_SIZE):
        variants_to_save = []
        for variant in Variant.rename_prefetched.filter(pk__in=variant_ids[i:i + DEFAULT_BATCH_SIZE]).order_by().only('name'):
            new_variant_name = variant._str()
            if new_variant_name != variant.name:
                variant.name = new_variant_name
                variants_to_save.append(variant)
        Variant.objects.bulk_update(variants_to_save, ['name'], skip_pre_save=True, batch_size=DEFAULT_BATCH_SIZE)


def replace_attribute_references(instance: FeatureAttribute, old_name: str):
    '''Propagates the loss of an attribute name, by a rename or by a merge into another attribute, to
    the references selecting it or writing it as a key.'''
    if old_name and old_name != instance.name:
        from .combo import Combo
        for part in ATTRIBUTE_PARTS:
            rename_in_models((Combo, *ingredient_models()), part, old_name, instance.name)


def remove_attribute_references(name: str):
    '''Propagates the deletion of an attribute to the references selecting it or writing it as a key.'''
    from .combo import Combo
    remove = partial(remove_references, name=name)
    for model in (Combo, *ingredient_models()):
        rewrite_rows(model, remove, references_filter(model, 'selector', name) | references_filter(model, 'key', name))
