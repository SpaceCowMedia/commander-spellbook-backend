from django.contrib import admin
from django.db.models.query import QuerySet
from django.http import HttpRequest
from spellbook.models import VariantAlias


@admin.register(VariantAlias)
class VariantAliasAdmin(admin.ModelAdmin):
    readonly_fields = ['updated', 'created']
    fields = ['id', 'updated', 'created', 'variant', 'description']
    list_display = ['__str__', 'variant', 'updated']
    search_fields = [
        '=pk',
        'variant__id',
        'description',
    ]
    raw_id_fields = ['variant']
    list_filter = [
        ('variant', admin.EmptyFieldListFilter)  # type: ignore for deprecated typing
    ]

    def get_queryset(self, request: HttpRequest) -> QuerySet[VariantAlias]:
        return super().get_queryset(request).select_related('variant')

    def get_readonly_fields(self, request: HttpRequest, obj: VariantAlias | None = None) -> list[str] | tuple[VariantAlias, ...]:
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj:
            readonly_fields.append('id')
        return readonly_fields
