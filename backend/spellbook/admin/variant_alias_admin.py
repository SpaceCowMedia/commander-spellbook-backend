from django.contrib import admin
from spellbook.models import VariantAlias


@admin.register(VariantAlias)
class VariantAliasAdmin(admin.ModelAdmin):
    fields = ['id', 'variant', 'description']
    list_display = ['__str__', 'variant', 'description']
    search_fields = ['id', 'variant__id', 'description']
    raw_id_fields = ['variant']
    list_filter = [
        ('variant', admin.EmptyFieldListFilter)
    ]
