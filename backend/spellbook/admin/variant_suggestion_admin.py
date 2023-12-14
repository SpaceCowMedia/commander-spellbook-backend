from typing import Any
from django.db.models import Count, Prefetch
from django.contrib import admin
from spellbook.models import VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion
from spellbook.models.utils import recipe
from .ingredient_admin import IngredientAdmin
from .utils import SpellbookModelAdmin, CardsCountListFilter


class CardUsedInVariantSuggestionAdminInline(IngredientAdmin):
    fields = ['card', *IngredientAdmin.fields]
    model = CardUsedInVariantSuggestion
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    min_num = 1
    max_num = VariantSuggestion.max_cards


class TemplateRequiredInVariantAdminInline(IngredientAdmin):
    fields = ['template', 'scryfall_query', *IngredientAdmin.fields]
    model = TemplateRequiredInVariantSuggestion
    verbose_name = 'Template'
    verbose_name_plural = 'Templates'
    max_num = VariantSuggestion.max_templates


class FeatureProducedInVariantAdminInline(admin.TabularInline):
    fields = ['feature']
    model = FeatureProducedInVariantSuggestion
    verbose_name = 'Feature'
    verbose_name_plural = 'Features'
    min_num = 1
    max_num = VariantSuggestion.max_features
    extra = 0


@admin.action(description='Mark selected suggestions as REJECTED')
def set_rejected(modeladmin, request, queryset):
    queryset.update(status=VariantSuggestion.Status.REJECTED)


@admin.register(VariantSuggestion)
class VariantSuggestionAdmin(SpellbookModelAdmin):
    save_as = True
    readonly_fields = ['id', 'suggested_by']
    fieldsets = [
        ('Generated', {'fields': [
            'id',
            'suggested_by']}),
        ('Editable', {'fields': [
            'status',
            'notes',
            'mana_needed',
            'other_prerequisites',
            'description']})
    ]
    inlines = [CardUsedInVariantSuggestionAdminInline, TemplateRequiredInVariantAdminInline, FeatureProducedInVariantAdminInline]
    list_filter = ['status', CardsCountListFilter]
    list_display = ['display_name', 'id', 'status']
    actions = [set_rejected]

    def display_name(self, obj):
        return recipe([str(card) for card in obj.prefetched_uses] + [str(template) for template in obj.prefetched_requires],
            [str(feature) for feature in obj.prefetched_produces])

    def get_queryset(self, request):
        return VariantSuggestion.objects \
            .prefetch_related(
                Prefetch('uses', to_attr='prefetched_uses'),
                Prefetch('requires', to_attr='prefetched_requires'),
                Prefetch('produces', to_attr='prefetched_produces')) \
            .alias(cards_count=Count('uses', distinct=True) + Count('requires', distinct=True))

    def save_model(self, request: Any, obj: Any, form: Any, change: Any) -> None:
        if not change:
            form.instance.suggested_by = request.user
        super().save_model(request, obj, form, change)
