from django.contrib import admin
from django.db.models import Prefetch, Q, QuerySet
from django.http import HttpRequest
from spellbook.models import Card, FeatureAttribute, Combo, FeatureNeededInCombo, FeatureOfCardAttribute, FeatureProducedInCombo, FeatureProducedInComboAttribute, replace_attribute_references
from .utils import MergeableModelAdmin, SpellbookAdminForm


class FeatureAttributeForm(SpellbookAdminForm):
    def used_in_combos(self) -> QuerySet[Combo]:
        '''The combos needing or producing a feature with the attribute, most recent first, each with
        the rows doing so.'''
        attribute = self.instance
        if attribute.pk is None:
            return Combo.objects.none()
        needing = FeatureNeededInCombo.objects.filter(Q(any_of_attributes=attribute) | Q(all_of_attributes=attribute) | Q(none_of_attributes=attribute)).values('combo_id')
        producing = FeatureProducedInComboAttribute.objects.filter(attribute=attribute).values('producer__combo_id')
        needed = FeatureNeededInCombo.objects.select_related('feature')
        return Combo.objects.filter(Q(pk__in=needing) | Q(pk__in=producing)).order_by('-created').prefetch_related(
            Prefetch('featureneededincombo_set', needed.filter(any_of_attributes=attribute), to_attr='needing_it_in_any_of'),
            Prefetch('featureneededincombo_set', needed.filter(all_of_attributes=attribute), to_attr='needing_it_in_all_of'),
            Prefetch('featureneededincombo_set', needed.filter(none_of_attributes=attribute), to_attr='needing_it_in_none_of'),
            Prefetch('featureproducedincombo_set', FeatureProducedInCombo.objects.filter(attributes=attribute).select_related('feature'), to_attr='producing_it'),
        )

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
