from django.contrib import admin
from django.db.models import QuerySet, Case, When
from django.utils.html import format_html
from spellbook.models import Feature, FeatureOfCard
from spellbook.models.scryfall import scryfall_link_for_query, scryfall_query_string_for_card_names, SCRYFALL_MAX_QUERY_LENGTH
from .utils import SpellbookModelAdmin
from .ingredient_admin import IngredientAdmin


class CardInFeatureAdminInline(IngredientAdmin):
    fields = ['card', *IngredientAdmin.fields]
    model = FeatureOfCard
    extra = 0
    autocomplete_fields = ['card']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


@admin.register(Feature)
class FeatureAdmin(SpellbookModelAdmin):
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fields = ['name', 'id', 'updated', 'created', 'utility', 'uncountable', 'description', 'scryfall_link']
    inlines = [CardInFeatureAdminInline]
    search_fields = ['name', 'cards__name']
    list_display = ['name', 'id', 'utility', 'updated']
    list_filter = ['utility']

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'produced_by_variants__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)  # type: ignore for deprecated typing

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

    @admin.display(description='Scryfall link')
    def scryfall_link(self, obj: Feature):
        card_names: list[str] = obj.cards.values_list('name', flat=True)  # type: ignore
        if card_names:
            query_string = scryfall_query_string_for_card_names(card_names)
            if len(query_string) <= SCRYFALL_MAX_QUERY_LENGTH:
                link = scryfall_link_for_query(query_string)
                plural = 's' if len(card_names) > 1 else ''
                return format_html('<a href="{}" target="_blank">Show card{} that produce this feature on scryfall</a>', link, plural)
            else:
                return 'Query too long for generating a scryfall link with all cards producing this feature'
        return None
