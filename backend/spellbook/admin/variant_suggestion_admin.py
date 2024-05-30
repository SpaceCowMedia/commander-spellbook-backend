from typing import Any
from django.db.models import Count
from django.contrib import admin
from spellbook.models import VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion
from .ingredient_admin import IngredientInCombinationAdmin
from .utils import SpellbookModelAdmin, CardsCountListFilter, sanitize_scryfall_query
from spellbook.utils import launch_job_command


class CardUsedInVariantSuggestionAdminInline(IngredientInCombinationAdmin):
    fields = ['card', *IngredientInCombinationAdmin.fields]
    model = CardUsedInVariantSuggestion
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    min_num = 1
    max_num = VariantSuggestion.max_cards


class TemplateRequiredInVariantAdminForm(IngredientInCombinationAdmin.form):
    def clean_scryfall_query(self):
        return sanitize_scryfall_query(self.cleaned_data['scryfall_query'])


class TemplateRequiredInVariantAdminInline(IngredientInCombinationAdmin):
    form = TemplateRequiredInVariantAdminForm
    fields = ['template', 'scryfall_query', *IngredientInCombinationAdmin.fields]
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
    ids = queryset.values_list('id', flat=True)
    queryset.update(status=VariantSuggestion.Status.REJECTED)
    launch_job_command(
        command='notify',
        user=request.user,
        args=['variant_suggestion_rejected', *map(str, ids)],
    )


@admin.register(VariantSuggestion)
class VariantSuggestionAdmin(SpellbookModelAdmin):
    save_as = True
    readonly_fields = ['id', 'suggested_by', 'comment']
    fieldsets = [
        ('General', {'fields': [
            'id',
            'suggested_by',
            'comment',
        ]}),
        ('Editable', {'fields': [
            'mana_needed',
            'other_prerequisites',
            'description',
            'spoiler',
        ]}),
        ('Review', {'fields': [
            'status',
            'notes',
        ]}),
    ]
    inlines = [CardUsedInVariantSuggestionAdminInline, TemplateRequiredInVariantAdminInline, FeatureProducedInVariantAdminInline]
    list_filter = ['status', CardsCountListFilter, 'spoiler']
    list_display = ['__str__', 'id', 'status', 'spoiler']
    actions = [set_rejected]
    search_fields = [
        'uses__card',
        'uses__card_unaccented',
        'uses__card_unaccented_simplified',
        'uses__card_unaccented_simplified_with_spaces',
        'requires__template',
        'produces__feature',
        'suggested_by__username',
        'notes',
        'comment',
    ]

    def get_queryset(self, request):
        return VariantSuggestion.objects.alias(cards_count=Count('uses', distinct=True) + Count('requires', distinct=True))

    def save_form(self, request: Any, form: Any, change: bool) -> Any:
        new_object = super().save_form(request, form, change)
        if change:
            if 'status' in form.changed_data:
                if new_object.status == VariantSuggestion.Status.ACCEPTED:
                    launch_job_command(
                        command='notify',
                        user=request.user,
                        args=['variant_suggestion_accepted', str(new_object.id)],
                    )
                elif new_object.status == VariantSuggestion.Status.REJECTED:
                    launch_job_command(
                        command='notify',
                        user=request.user,
                        args=['variant_suggestion_rejected', str(new_object.id)],
                    )
        return new_object

    def save_model(self, request: Any, obj: Any, form: Any, change: bool):
        if not change:
            form.instance.suggested_by = request.user
        super().save_model(request, obj, form, change)
