from django.contrib import admin
from django.db.models import QuerySet, Case, When
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

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'produced_by_variants__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)

    def sort_search_results(self, request, queryset: QuerySet, search_term: str) -> QuerySet:
        search_terms = [sub_term.strip() for term in search_term.split(' | ') for sub_term in term.split(' + ') if sub_term.strip()]
        cases: list[When] = []
        for i, term in enumerate(search_terms):
            points = len(search_terms) - i
            cases.append(When(name__iexact=term, then=10 * points + 4))
            cases.append(When(name__istartswith=term, then=10 * points + 3))
            cases.append(When(name__icontains=term, then=10 * points + 2))
        return queryset.alias(
            match_points=Case(
                *cases,
                default=1,
            )
        ).order_by('-match_points')
