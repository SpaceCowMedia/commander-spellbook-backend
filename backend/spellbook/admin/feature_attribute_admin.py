from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest, JsonResponse
from django.urls import path
from spellbook.models import Card, FeatureAttribute, Combo, FeatureNeededInCombo, FeatureOfCardAttribute, FeatureProducedInComboAttribute, replace_attribute_references
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

    def get_urls(self):
        return [
            path('names/', self.admin_site.admin_view(self.names_view), name='spellbook_featureattribute_names'),
            *super().get_urls(),
        ]

    def names_view(self, request: HttpRequest) -> JsonResponse:
        '''The names of every attribute, which the dictionary editor suggests as keys.'''
        return JsonResponse({'names': list(FeatureAttribute.objects.order_by('name').values_list('name', flat=True))})

    def merge_objects(self, from_obj: FeatureAttribute, to_obj: FeatureAttribute) -> None:
        merge_feature_attribute(from_obj, to_obj)


def merge_feature_attribute(from_obj: FeatureAttribute, to_obj: FeatureAttribute):
    attribute_rows: tuple[type[FeatureOfCardAttribute] | type[FeatureProducedInComboAttribute], ...] = (FeatureOfCardAttribute, FeatureProducedInComboAttribute)
    for through in attribute_rows:
        # a producer holding both keeps the text of the target, unless it gives it none
        targets = {row.producer_id: row for row in through.objects.filter(attribute=to_obj)}
        for row in through.objects.filter(attribute=from_obj, producer_id__in=targets):
            target = targets[row.producer_id]
            if row.value and not target.value:
                target.value = row.value
                target.save(update_fields=['value'])
            row.delete()
        through.objects.filter(attribute=from_obj).update(attribute=to_obj)
    for through, field in (
        (FeatureNeededInCombo.any_of_attributes.through, 'any_of_attributes'),
        (FeatureNeededInCombo.all_of_attributes.through, 'all_of_attributes'),
        (FeatureNeededInCombo.none_of_attributes.through, 'none_of_attributes'),
    ):
        through.objects.filter(featureattribute_id=from_obj.id, **{f'featureneededincombo__{field}': to_obj.id}).delete()
        through.objects.filter(featureattribute_id=from_obj.id).update(featureattribute_id=to_obj.id)
    replace_attribute_references(to_obj, from_obj.name)
