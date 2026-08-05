import re
from functools import partial
from typing import Callable, Iterable, Sequence, TypeVar
from django.db.models import Q
from .card import FeatureOfCard
from .combo import CardInCombo, Combo, FeatureNeededInCombo, TemplateInCombo
from .feature import Feature
from .feature_attribute import FeatureAttribute
from .ingredient import Ingredient
from .utils import DEFAULT_BATCH_SIZE
from .variant import Variant


_T = TypeVar('_T')

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


def references_filter(model: type[Combo] | type[Ingredient], referenced: type[Feature] | type[FeatureAttribute], name: str) -> Q:
    '''Matches the rows of the given model whose text could contain a reference to the given feature or
    attribute name, so that a rename only loads the rows that mention it, no matter how they relate to
    it: a feature is referenced as the key of a replacement, while an attribute is only referenced as
    its selector.'''
    reference = f'[[{name}' if issubclass(referenced, Feature) else f'${name}'
    query = Q()
    for field in model.text_fields_with_references():
        query |= Q(**{f'{field}__icontains': reference})
    return query


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


def replace_feature_references(instance: Feature, old_name: str):
    '''Propagates the loss of a feature name, by a rename or by a merge into another feature, to
    everything referencing it in a text or displaying it in a recipe.'''
    if old_name and old_name != instance.name:
        replace_feature_references_in_combos(instance, old_name)
        replace_feature_references_in_variants(instance, old_name)


def replace_feature_references_in_combos(instance: Feature, old_name: str):
    new_name = instance.name
    replacement = partial(replace_feature_reference, old_name, new_name)
    ingredient_fields = Ingredient.text_fields_with_references()
    ingredient_filter = references_filter(Ingredient, Feature, old_name)
    # every row loaded here is rewritten, so the order they come in is irrelevant
    cards_in_combos = list(CardInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
    templates_in_combos = list(TemplateInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
    features_in_combos = list(FeatureNeededInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
    feature_of_card_fields = FeatureOfCard.text_fields_with_references()
    features_of_cards = list(FeatureOfCard.objects.filter(references_filter(FeatureOfCard, Feature, old_name)).order_by().only(*feature_of_card_fields))
    combo_text_fields = Combo.text_fields_with_references()
    combo_fields = [*combo_text_fields, *Combo.recipe_fields()]
    combos = list(Combo.recipes_prefetched.filter(
        # the recipe of a combo can only change if its name displays the old one
        Q(name__contains=old_name) | references_filter(Combo, Feature, old_name),
    ).order_by().only(*combo_fields))
    combos_to_update = {combo.pk: combo for combo in replace_in_text_fields(combos, combo_text_fields, replacement)}
    combo: Combo
    for combo in combos:
        if combo.update_recipe_from_data():
            combos_to_update[combo.pk] = combo
    Combo.objects.bulk_update(combos_to_update.values(), combo_fields, batch_size=DEFAULT_BATCH_SIZE)
    CardInCombo.objects.bulk_update(replace_in_text_fields(cards_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
    TemplateInCombo.objects.bulk_update(replace_in_text_fields(templates_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
    FeatureNeededInCombo.objects.bulk_update(replace_in_text_fields(features_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
    FeatureOfCard.objects.bulk_update(replace_in_text_fields(features_of_cards, feature_of_card_fields, replacement), feature_of_card_fields, batch_size=DEFAULT_BATCH_SIZE)


def replace_feature_references_in_variants(instance: Feature, old_name: str):
    '''Recomputes the names of the variants displaying the old name, which is the only part of a variant
    a feature name can reach: variants hold no text of their own to reference it from.'''
    # the ids are taken upfront because the update itself makes the rows stop matching that condition,
    # unordered because rewriting them all makes the order they come in irrelevant
    variant_ids = list(Variant.objects.filter(produces=instance, name__contains=old_name).order_by().values_list('pk', flat=True))
    # only the name is loaded and written, so pre_save is skipped to keep the other fields deferred
    for i in range(0, len(variant_ids), DEFAULT_BATCH_SIZE):
        variants_to_save = []
        for variant in Variant.recipes_prefetched.filter(pk__in=variant_ids[i:i + DEFAULT_BATCH_SIZE]).order_by().only('name'):
            new_variant_name = variant._str()
            if new_variant_name != variant.name:
                variant.name = new_variant_name
                variants_to_save.append(variant)
        Variant.objects.bulk_update(variants_to_save, ['name'], skip_pre_save=True, batch_size=DEFAULT_BATCH_SIZE)


def replace_feature_reference(old_name: str, new_name: str, text: str) -> str:
    def replacement_with_fallback(key: str, face: str | None, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
        if key.lower() != old_name.lower():
            return otherwise
        return format_feature_replacement(new_name, face, alias, selector, postfix_alias)
    return FEATURE_REPLACEMENT_PATTERN.sub(
        lambda m: replacement_with_fallback(m.group('key'), m.group('face'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
        text,
    )


def replace_attribute_references(instance: FeatureAttribute, old_name: str):
    new_name = instance.name
    if old_name and old_name != new_name:
        replacement = partial(replace_attribute_reference, old_name, new_name)
        ingredient_fields = Ingredient.text_fields_with_references()
        ingredient_filter = references_filter(Ingredient, FeatureAttribute, old_name)
        feature_of_card_fields = FeatureOfCard.text_fields_with_references()
        combo_text_fields = Combo.text_fields_with_references()
        # every row loaded here is rewritten, so the order they come in is irrelevant
        combos = list(Combo.objects.filter(references_filter(Combo, FeatureAttribute, old_name)).order_by().only(*combo_text_fields))
        cards_in_combos = list(CardInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
        templates_in_combos = list(TemplateInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
        features_in_combos = list(FeatureNeededInCombo.objects.filter(ingredient_filter).order_by().only(*ingredient_fields))
        features_of_cards = list(FeatureOfCard.objects.filter(references_filter(FeatureOfCard, FeatureAttribute, old_name)).order_by().only(*feature_of_card_fields))
        Combo.objects.bulk_update(replace_in_text_fields(combos, combo_text_fields, replacement), combo_text_fields, batch_size=DEFAULT_BATCH_SIZE)
        CardInCombo.objects.bulk_update(replace_in_text_fields(cards_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        TemplateInCombo.objects.bulk_update(replace_in_text_fields(templates_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureNeededInCombo.objects.bulk_update(replace_in_text_fields(features_in_combos, ingredient_fields, replacement), ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureOfCard.objects.bulk_update(replace_in_text_fields(features_of_cards, feature_of_card_fields, replacement), feature_of_card_fields, batch_size=DEFAULT_BATCH_SIZE)


def replace_attribute_reference(old_name: str, new_name: str, text: str) -> str:
    def replacement_with_fallback(key: str, face: str | None, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
        # a numeric selector is a position among the needed features, never an attribute name
        if selector is None or selector.isdigit() or selector.lower() != old_name.lower():
            return otherwise
        return format_feature_replacement(key, face, alias, new_name, postfix_alias)
    return FEATURE_REPLACEMENT_PATTERN.sub(
        lambda m: replacement_with_fallback(m.group('key'), m.group('face'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
        text,
    )
