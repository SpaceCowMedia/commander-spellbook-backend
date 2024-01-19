from typing import Any
from django.contrib import admin
from django.db.models import QuerySet, Case, When
from django.http import HttpRequest
from spellbook.models import Feature
from .utils import SpellbookModelAdmin


class CardInFeatureAdminInline(admin.StackedInline):
    model = Feature.cards.through
    extra = 1
    autocomplete_fields = ['card']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


@admin.register(Feature)
class FeatureAdmin(SpellbookModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'utility', 'description']}),
    ]
    inlines = [CardInFeatureAdminInline]
    search_fields = ['name', 'cards__name']
    list_display = ['name', 'id', 'utility']
    list_filter = ['utility']

    def lookup_allowed(self, lookup: str, value: str) -> bool:
        return super().lookup_allowed(lookup, value) or lookup in (
            'produced_by_variants__id',
        )

    def get_search_results(self, request: HttpRequest, queryset: QuerySet[Any], search_term: str) -> tuple[QuerySet[Any], bool]:
        queryset, duplicates = super().get_search_results(request, queryset, search_term)
        return queryset.alias(
            match_points=Case(
                When(name__iexact=search_term, then=5),
                When(name__istartswith=search_term, then=4),
                default=1,
            )
        ).order_by('-match_points', 'name'), duplicates
