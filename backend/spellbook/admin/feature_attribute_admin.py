from django.contrib import admin
from django.db.models import Q
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
    search_fields = ['name']
    list_display = ['name', 'id']
