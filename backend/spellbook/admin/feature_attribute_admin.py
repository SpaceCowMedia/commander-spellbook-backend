from django.contrib import admin
from django.db.models import Q, QuerySet
from django.http import HttpRequest
from spellbook.models import FeatureAttribute, Combo
from .utils import SpellbookModelAdmin, SpellbookAdminForm


class FeatureAttributeForm(SpellbookAdminForm):
    def used_in_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            Q(featureneededincombo__any_of_attributes=self.instance) | Q(featureneededincombo__all_of_attributes=self.instance) | Q(featureneededincombo__none_of_attributes=self.instance) | Q(featureproducedincombo__attributes=self.instance)
        ).order_by('-created')


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
                    Q(used_as_attribute_in_featureofcard__feature_id=feature_id) | Q(used_as_attribute_in_featureproducedincombo__feature_id=feature_id),
                )
            except ValueError:
                pass
        return super().get_search_results(request, queryset, search_term)
