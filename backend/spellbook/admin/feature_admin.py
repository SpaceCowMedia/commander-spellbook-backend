from typing import Any
from django.contrib import admin
from django.db.models import QuerySet, TextField, Count
from django.forms.widgets import Textarea
from django.http import HttpRequest
from django.utils.html import format_html
from spellbook.models import Feature, FeatureOfCard, Combo
from spellbook.models.scryfall import scryfall_link_for_query, scryfall_query_string_for_card_names, SCRYFALL_MAX_QUERY_LENGTH
from .utils import SpellbookModelAdmin, SpellbookAdminForm
from .ingredient_admin import IngredientAdmin


class CardInFeatureAdminInline(IngredientAdmin):
    fields = ['card', *IngredientAdmin.fields, 'easy_prerequisites', 'notable_prerequisites', 'attributes']
    model = FeatureOfCard
    extra = 0
    autocomplete_fields = ['card', 'attributes']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'
    formfield_overrides = {
        TextField: {'widget': Textarea(attrs={'rows': 1, 'cols': 25, 'style': 'resize: vertical; min-height: 2em;'})},
    }


class FeatureForm(SpellbookAdminForm):
    def child_feature_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.prefetch_related('produces').alias(
            produced_count=Count('produces', distinct=True),
            needed_count=Count('needs', distinct=True),
        ).filter(
            produced_count=1,
            needed_count=1,
            uses=None,
            requires=None,
            needs=self.instance,
        ).order_by('name')

    def parent_feature_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.prefetch_related('needs').alias(
            produced_count=Count('produces', distinct=True),
            needed_count=Count('needs', distinct=True),
        ).filter(
            produced_count=1,
            needed_count=1,
            uses=None,
            requires=None,
            produces=self.instance,
        ).order_by('name')

    def needed_by_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            needs=self.instance,
        ).exclude(
            pk__in=self.child_feature_combos(),
        )

    def produced_by_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            produces=self.instance,
        ).exclude(
            pk__in=self.parent_feature_combos(),
        )


@admin.register(Feature)
class FeatureAdmin(SpellbookModelAdmin):
    form = FeatureForm
    readonly_fields = [
        'id',
        'scryfall_link',
        'updated',
        'created',
    ]
    fields = [
        'name',
        'id',
        'updated',
        'created',
        'status',
        'uncountable',
        'description',
        'scryfall_link',
    ]
    inlines = [CardInFeatureAdminInline]
    search_fields = [
        '=pk',
        'name',
        'cards__name',
    ]
    list_display = [
        'name',
        'id',
        'status',
        'produced_by_count',
        'updated',
    ]
    list_filter = ['status']

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'produced_by_variants__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)  # type: ignore for deprecated typing

    @admin.display(description='Scryfall link')
    def scryfall_link(self, obj: Feature):
        card_names: list[str] = obj.cards.distinct().values_list('name', flat=True)  # type: ignore
        if card_names:
            query_string = scryfall_query_string_for_card_names(card_names)
            if len(query_string) <= SCRYFALL_MAX_QUERY_LENGTH:
                link = scryfall_link_for_query(query_string)
                plural = 's' if len(card_names) > 1 else ''
                return format_html('<a href="{}" target="_blank">Show card{} that produce this feature on scryfall</a>', link, plural)
            else:
                return 'Query too long for generating a scryfall link with all cards producing this feature'
        return None

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        return super().get_queryset(request).annotate(
            produced_by_count=Count('produced_by_variants', distinct=True) + Count('cards', distinct=True),
        ).order_by(*Feature._meta.ordering or [])

    @admin.display(description='Produced by variants or cards', ordering='produced_by_count')
    def produced_by_count(self, obj: Feature):
        if obj.pk is None:
            return 0
        return obj.produced_by_count  # type: ignore
