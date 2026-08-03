from itertools import chain
from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from spellbook.models import Card, CardInCombo, DEFAULT_BATCH_SIZE, FeatureAttribute, FeatureNeededInCombo, FeatureOfCard, Combo, TemplateInCombo, Ingredient
from spellbook.variants.replacements import FEATURE_REPLACEMENT_PATTERN, format_feature_replacement
from .utils import SpellbookModelAdmin, SpellbookAdminForm


class FeatureAttributeForm(SpellbookAdminForm):
    def used_in_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            Q(featureneededincombo__any_of_attributes=self.instance) | Q(featureneededincombo__all_of_attributes=self.instance) | Q(featureneededincombo__none_of_attributes=self.instance) | Q(featureproducedincombo__attributes=self.instance)
        ).distinct().order_by('-created')

    def used_in_cards(self):
        if self.instance.pk is None:
            return Card.objects.none()
        return Card.objects.filter(
            featureofcard__attributes=self.instance
        ).distinct().order_by('-added')


@admin.register(FeatureAttribute)
class FeatureAttributeAdmin(SpellbookModelAdmin):
    form = FeatureAttributeForm
    readonly_fields = ['id']
    fields = ['id', 'name']
    search_fields = [
        '=pk',
        'name',
    ]
    list_display = ['name', 'id']

    def get_search_results(self, request: HttpRequest, queryset: QuerySet[FeatureAttribute], search_term: str):
        feature_id = request.GET.get('feature_id')
        if feature_id is not None:
            try:
                queryset = queryset.filter(
                    Q(name__iexact=search_term) | Q(used_as_attribute_in_featureofcard__feature_id=feature_id) | Q(used_as_attribute_in_featureproducedincombo__feature_id=feature_id),
                )
            except ValueError:
                pass
        return super().get_search_results(request, queryset, search_term)

    def after_save_related(self, request, form: FeatureAttributeForm, formsets, change):
        if change:
            old_name: str | None = form.initial.get('name')
            instance: FeatureAttribute = form.instance
            if old_name is not None and old_name != instance.name:
                replace_attribute_references(instance, old_name)
        super().after_save_related(request, form, formsets, change)


def replace_attribute_references(instance: FeatureAttribute, old_name: str):
    new_name = instance.name
    if old_name and old_name != new_name:
        ingredient_fields = Ingredient.text_fields_with_references()
        combo_text_fields = Combo.text_fields_with_references()
        feature_of_card_fields = FeatureOfCard.text_fields_with_references()
        combo_ids_qs = Combo.objects.filter(
            Q(featureneededincombo__any_of_attributes=instance) | Q(featureneededincombo__all_of_attributes=instance) | Q(featureneededincombo__none_of_attributes=instance) | Q(featureproducedincombo__attributes=instance)
        ).values('pk').distinct()
        combos = list(Combo.objects.filter(pk__in=combo_ids_qs).only(*combo_text_fields))
        cards_in_combos = list(CardInCombo.objects.filter(combo_id__in=combo_ids_qs).only(*ingredient_fields))
        templates_in_combos = list(TemplateInCombo.objects.filter(combo_id__in=combo_ids_qs).only(*ingredient_fields))
        features_in_combos = list(FeatureNeededInCombo.objects.filter(combo_id__in=combo_ids_qs).only(*ingredient_fields))
        for ingredient in chain(cards_in_combos, templates_in_combos, features_in_combos):
            for field in ingredient_fields:
                setattr(ingredient, field, replace_attribute_reference(old_name, new_name, getattr(ingredient, field)))
        for combo in combos:
            for field in combo_text_fields:
                setattr(combo, field, replace_attribute_reference(old_name, new_name, getattr(combo, field)))
        features_of_cards = list(FeatureOfCard.objects.filter(attributes=instance).only(*feature_of_card_fields))
        for feature_of_card in features_of_cards:
            for field in feature_of_card_fields:
                setattr(feature_of_card, field, replace_attribute_reference(old_name, new_name, getattr(feature_of_card, field)))
        Combo.objects.bulk_update(combos, combo_text_fields, batch_size=DEFAULT_BATCH_SIZE)
        CardInCombo.objects.bulk_update(cards_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        TemplateInCombo.objects.bulk_update(templates_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureNeededInCombo.objects.bulk_update(features_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureOfCard.objects.bulk_update(features_of_cards, feature_of_card_fields, batch_size=DEFAULT_BATCH_SIZE)


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
