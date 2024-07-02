from django.contrib import admin
from spellbook.models import FeatureAttribute
from .utils import SpellbookModelAdmin


@admin.register(FeatureAttribute)
class FeatureAttributeAdmin(SpellbookModelAdmin):
    readonly_fields = ['id']
    fields = ['id', 'name']
    search_fields = ['name']
    list_display = ['name', 'id']
