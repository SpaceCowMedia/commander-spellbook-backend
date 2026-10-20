import re
from functools import partial
from typing import TYPE_CHECKING, Any, Callable, Collection, Iterable, Literal, Sequence, TypeVar
from django.db.models import Manager, Q
from .utils import DEFAULT_BATCH_SIZE
if TYPE_CHECKING:
    from .combo import Combo
    from .feature import Feature
    from .feature_attribute import FeatureAttribute
    from .ingredient import Ingredient


_T = TypeVar('_T')

# The characters of the reference syntax, each defined once: every pattern, formatter, validator and
# help text is built from them. Migrations keep a copy of the syntax of their time instead.
ALIAS_PREFIX = '!'
LINE_REFERENCE_PREFIX = '#'
REFERENCE_PREFIXES = (ALIAS_PREFIX, LINE_REFERENCE_PREFIX)
REPLACEMENT_BRACKETS = ('[[', ']]')
INCLUSION_BRACKETS = ('{{', '}}')
FACE_MARKER = '#'
SELECTOR_MARKER = '$'
ALIAS_MARKER = '|'
# the characters a feature or attribute name cannot hold, since they end the key of a reference
RESERVED_CHARACTERS = (SELECTOR_MARKER, ALIAS_MARKER)


def escaped(*parts: str) -> str:
    return ''.join(map(re.escape, parts))


def character_class(*excluded: str) -> str:
    '''The regex class of the characters a part of a reference can hold: none of the excluded ones, on a single line.'''
    return f'[^{escaped(*sorted(set("".join(excluded))))}\\n]'


def bracketed(brackets: tuple[str, str], content: str) -> str:
    return f'{brackets[0]}{content}{brackets[1]}'


def optional(marker: str, part: str | None) -> str:
    return '' if part is None else f'{marker}{part}'


def between(brackets: tuple[str, str]) -> str:
    '''The regex of whatever a text holds between the given brackets, unless they are part of a longer
    run of the same brackets, which is plain text.'''
    run = re.escape(brackets[0][0])
    return f'(?<!{run}){re.escape(brackets[0])}(?!{run}).*?{re.escape(brackets[1])}'


PREFIX_ALTERNATIVES = '|'.join(map(re.escape, REFERENCE_PREFIXES))
NOT_A_PREFIX = f'(?!{PREFIX_ALTERNATIVES})'
REFERENCE_PREFIX_REGEX = f'^(?:{PREFIX_ALTERNATIVES})'
ALIAS_NAME = character_class(*REFERENCE_PREFIXES, *REPLACEMENT_BRACKETS, *INCLUSION_BRACKETS, FACE_MARKER, *RESERVED_CHARACTERS) + '+'
RESERVED_CHARACTERS_REGEX = '|'.join(map(re.escape, RESERVED_CHARACTERS))

# A feature replacement looks like [[key#face$selector|alias]], where every part but the key is optional:
# - #face selects which face of a multi-faced card to display;
# - $selector picks one among the multiple replacements of the same feature, either by position
#   (the position of the needed feature row of the combo the text belongs to) or by attribute name;
# - |alias names the reference, so that the rest of the text can repeat it as [[!alias]] or {{!alias}}.
FEATURE_REPLACEMENT_PATTERN = re.compile(
    f'{re.escape(REPLACEMENT_BRACKETS[0])}'
    f'(?P<key>{NOT_A_PREFIX}{character_class(*RESERVED_CHARACTERS)}+?)'
    f'(?:{re.escape(FACE_MARKER)}(?P<face>[1-9]\\d*))?'
    f'(?:{re.escape(SELECTOR_MARKER)}(?P<selector>{character_class(*RESERVED_CHARACTERS, REPLACEMENT_BRACKETS[1])}+))?'
    f'(?:{re.escape(ALIAS_MARKER)}(?P<alias>{ALIAS_NAME}))?'
    f'{re.escape(REPLACEMENT_BRACKETS[1])}'
)

# A feature inclusion looks like {{key$selector}}, where the selector is optional: it is replaced with
# the text box it appears in, taken from every combo or card feature producing that feature, so that
# those texts are written where they are mentioned instead of being appended. The optional selector
# picks among the producers the same way the one of a replacement picks among the replacements.
FEATURE_INCLUSION_PATTERN = re.compile(
    f'{re.escape(INCLUSION_BRACKETS[0])}'
    f'(?P<key>{NOT_A_PREFIX}{character_class(*RESERVED_CHARACTERS, *INCLUSION_BRACKETS)}+?)'
    f'(?:{re.escape(SELECTOR_MARKER)}(?P<selector>{character_class(*RESERVED_CHARACTERS, *INCLUSION_BRACKETS)}+))?'
    f'{re.escape(INCLUSION_BRACKETS[1])}'
)

ALIAS_USE_PATTERN = re.compile(
    f'{escaped(REPLACEMENT_BRACKETS[0], ALIAS_PREFIX)}(?P<replaced>{ALIAS_NAME}){re.escape(REPLACEMENT_BRACKETS[1])}'
    f'|{escaped(INCLUSION_BRACKETS[0], ALIAS_PREFIX)}(?P<included>{ALIAS_NAME}){re.escape(INCLUSION_BRACKETS[1])}'
)

# {{#Z}} points at the Zth line of its text, {{#+X}} at the line X lines below, {{#-Y}} at the one Y lines above
LINE_REFERENCE_PATTERN = re.compile(f'{escaped(INCLUSION_BRACKETS[0], LINE_REFERENCE_PREFIX)}(?P<sign>[+-]?)(?P<number>\\d+){re.escape(INCLUSION_BRACKETS[1])}')

# whatever a text holds between double brackets, which has to be one of the references above
REFERENCE_PATTERN = re.compile(f'{between(REPLACEMENT_BRACKETS)}|{between(INCLUSION_BRACKETS)}')


def format_feature_replacement(key: str, face: str | None = None, selector: str | None = None, alias: str | None = None) -> str:
    '''Writes a feature replacement from its parts, the inverse of FEATURE_REPLACEMENT_PATTERN.'''
    return bracketed(REPLACEMENT_BRACKETS, key + optional(FACE_MARKER, face) + optional(SELECTOR_MARKER, selector) + optional(ALIAS_MARKER, alias))


def format_feature_inclusion(key: str, selector: str | None = None) -> str:
    '''Writes a feature inclusion from its parts, the inverse of FEATURE_INCLUSION_PATTERN.'''
    return bracketed(INCLUSION_BRACKETS, key + optional(SELECTOR_MARKER, selector))


def format_alias_replacement(alias: str) -> str:
    return bracketed(REPLACEMENT_BRACKETS, ALIAS_PREFIX + alias)


def format_alias_inclusion(alias: str) -> str:
    return bracketed(INCLUSION_BRACKETS, ALIAS_PREFIX + alias)


def format_line_reference(number: int | str, sign: str = '') -> str:
    return bracketed(INCLUSION_BRACKETS, f'{LINE_REFERENCE_PREFIX}{sign}{number}')


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
    '''Writes every alias a text uses as the reference defining it, so that whatever reads the result
    only meets feature names. An alias is known to the whole text defining it, before its definition
    too, and one the text does not define is left as written.'''
    definitions = dict[str, re.Match[str]]()
    for match in FEATURE_REPLACEMENT_PATTERN.finditer(text):
        if match['alias']:
            definitions.setdefault(match['alias'], match)

    def expand(use: re.Match[str]) -> str:
        definition = definitions.get(use['replaced'] or use['included'])
        if definition is None:
            return use[0]
        if use['replaced']:
            return format_feature_replacement(definition['key'], definition['face'], definition['selector'])
        return format_feature_inclusion(definition['key'], definition['selector'])

    return ALIAS_USE_PATTERN.sub(expand, text) if definitions else text


def references_to_features_not_needed(texts: Iterable[str], needed_feature_names: Collection[str]) -> list[str]:
    '''The feature replacements and inclusions in the texts of a combo whose key is not the name of a
    feature the combo needs, each once, sorted. Names are matched exactly, the way the texts of a variant
    resolve them. An alias use needs no check of its own, since its definition is one of them.'''
    return sorted({
        match[0]
        for text in texts
        for pattern in (FEATURE_REPLACEMENT_PATTERN, FEATURE_INCLUSION_PATTERN)
        for match in pattern.finditer(text)
        if match['key'] not in needed_feature_names
    })


# A feature is named by the key of a reference, an attribute by its selector
ReferencePart = Literal['key', 'selector']


def ingredient_models() -> tuple[type[Ingredient], ...]:
    '''The models besides combos whose rows hold texts with references.'''
    from .card import FeatureOfCard
    from .combo import CardInCombo, FeatureNeededInCombo, TemplateInCombo
    return CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureOfCard


def references_filter(model: type[Combo] | type[Ingredient], part: ReferencePart, name: str) -> Q:
    '''Matches the rows of the given model whose texts could reference the given name as the given part
    of a reference, so that a rename only loads the rows that mention it.'''
    starts = [REPLACEMENT_BRACKETS[0] + name, INCLUSION_BRACKETS[0] + name] if part == 'key' else [SELECTOR_MARKER + name]
    query = Q()
    for field in model.text_fields_with_references():
        for start in starts:
            query |= Q(**{f'{field}__icontains': start})
    return query


def rename_references(text: str, part: ReferencePart, old_name: str, new_name: str) -> str:
    '''Renames a feature or an attribute in the references of a text. Names are matched ignoring case,
    the way they are unique, and a numeric selector is a position, never an attribute.'''
    def rename(match: re.Match[str], formatter: Callable[..., str]) -> str:
        name = match[part]
        if name is None or name.lower() != old_name.lower() or (part == 'selector' and name.isdigit()):
            return match[0]
        return formatter(**(match.groupdict() | {part: new_name}))

    text = FEATURE_REPLACEMENT_PATTERN.sub(partial(rename, formatter=format_feature_replacement), text)
    return FEATURE_INCLUSION_PATTERN.sub(partial(rename, formatter=format_feature_inclusion), text)


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


def rename_in_rows(model: type[Combo] | type[Ingredient], rename: Callable[[str], str], rows_filter: Q) -> None:
    '''Renames in the texts of the rows of the model matching the filter, saving only the rows that
    changed. Every row loaded is rewritten, so the order they come in is irrelevant.'''
    fields = model.text_fields_with_references()
    manager: Manager[Any] = model._default_manager
    rows = manager.filter(rows_filter).order_by().only(*fields)
    manager.bulk_update(replace_in_text_fields(rows, fields, rename), fields, batch_size=DEFAULT_BATCH_SIZE)


def rename_in_models(models: Iterable[type[Combo] | type[Ingredient]], part: ReferencePart, old_name: str, new_name: str) -> Callable[[str], str]:
    '''Renames a feature or an attribute in the texts of the given models that mention it, and returns
    the rename for the texts left to the caller.'''
    rename = partial(rename_references, part=part, old_name=old_name, new_name=new_name)
    for model in models:
        rename_in_rows(model, rename, references_filter(model, part, old_name))
    return rename


def replace_feature_references(instance: Feature, old_name: str):
    '''Propagates the loss of a feature name, by a rename or by a merge into another feature, to
    everything referencing it in a text or displaying it in a recipe.'''
    if old_name and old_name != instance.name:
        replace_feature_references_in_combos(instance, old_name)
        replace_feature_references_in_variants(instance, old_name)


def replace_feature_references_in_combos(instance: Feature, old_name: str):
    from .combo import Combo
    rename = rename_in_models(ingredient_models(), 'key', old_name, instance.name)
    combo_text_fields = Combo.text_fields_with_references()
    combo_recipe_fields = Combo.recipe_fields()
    combos = list(Combo.rename_prefetched.filter(
        Q(needs=instance, name__contains=old_name) | Q(produces=instance, name__contains=old_name) | Q(removes=instance, name__contains=old_name) | references_filter(Combo, 'key', old_name),
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
    if old_name and old_name != instance.name:
        from .combo import Combo
        rename_in_models((Combo, *ingredient_models()), 'selector', old_name, instance.name)
