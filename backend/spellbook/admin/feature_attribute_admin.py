from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from spellbook.models import Card, FeatureAttribute, Combo, FeatureNeededInCombo, FeatureOfCard, FeatureProducedInCombo, replace_attribute_references
from .utils import MergeableModelAdmin, SpellbookAdminForm


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
class FeatureAttributeAdmin(MergeableModelAdmin):
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

    def merge_objects(self, from_obj: FeatureAttribute, to_obj: FeatureAttribute) -> None:
        merge_feature_attribute(from_obj, to_obj)


def merge_feature_attribute(from_obj: FeatureAttribute, to_obj: FeatureAttribute):
    FeatureOfCard.attributes.through.objects.filter(featureattribute_id=from_obj.id, featureofcard__attributes=to_obj.id).delete()
    FeatureOfCard.attributes.through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    FeatureProducedInCombo.attributes.through.objects.filter(featureattribute_id=from_obj.id, featureproducedincombo__attributes=to_obj.id).delete()
    FeatureProducedInCombo.attributes.through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    FeatureNeededInCombo.any_of_attributes.through.objects.filter(featureattribute_id=from_obj.id, featureneededincombo__any_of_attributes=to_obj.id).delete()
    FeatureNeededInCombo.any_of_attributes.through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    FeatureNeededInCombo.all_of_attributes.through.objects.filter(featureattribute_id=from_obj.id, featureneededincombo__all_of_attributes=to_obj.id).delete()
    FeatureNeededInCombo.all_of_attributes.through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    FeatureNeededInCombo.none_of_attributes.through.objects.filter(featureattribute_id=from_obj.id, featureneededincombo__none_of_attributes=to_obj.id).delete()
    FeatureNeededInCombo.none_of_attributes.through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    replace_attribute_references(to_obj, from_obj.name)
