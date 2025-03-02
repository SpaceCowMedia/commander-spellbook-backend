from typing import Any
from django.contrib import admin
from django.utils import timezone
from spellbook.models import VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion
from .ingredient_admin import IngredientInCombinationAdmin
from .utils import SpellbookModelAdmin, CardCountListFilter
from spellbook.utils import launch_job_command


class CardUsedInVariantSuggestionAdminInline(IngredientInCombinationAdmin):
    fields = ['card', *IngredientInCombinationAdmin.fields]
    model = CardUsedInVariantSuggestion
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    min_num = 1
    max_num = VariantSuggestion.max_cards


class TemplateRequiredInVariantAdminInline(IngredientInCombinationAdmin):
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
    queryset.update(status=VariantSuggestion.Status.REJECTED, updated=timezone.now())
    ids = queryset.exclude(suggested_by=request.user).values_list('id', flat=True)
    launch_job_command(
        command='notify',
        user=request.user,
        args=['variant_suggestion_rejected', *map(str, ids)],
        allow_multiples=True,
    )


@admin.register(VariantSuggestion)
class VariantSuggestionAdmin(SpellbookModelAdmin):
    save_as = True
    readonly_fields = ['id', 'suggested_by', 'updated', 'created']
    fieldsets = [
        ('General', {'fields': [
            'id',
            'suggested_by',
            'comment',
            'updated',
            'created',
        ]}),
        ('Editable', {'fields': [
            'mana_needed',
            'easy_prerequisites',
            'notable_prerequisites',
            'description',
            'spoiler',
        ]}),
        ('Review', {'fields': [
            'status',
            'notes',
        ]}),
    ]
    inlines = [CardUsedInVariantSuggestionAdminInline, TemplateRequiredInVariantAdminInline, FeatureProducedInVariantAdminInline]
    list_filter = ['status', CardCountListFilter, 'spoiler']
    list_display = ['name', 'id', 'status', 'spoiler', 'updated', 'created']
    actions = [set_rejected]
    search_fields = [
        '=pk',
        '=suggested_by__username',
        'uses__card',
        'uses__card_unaccented',
        'uses__card_unaccented_simplified',
        'uses__card_unaccented_simplified_with_spaces',
        'requires__template',
        'produces__feature',
        'notes',
        'comment',
    ]

    def get_readonly_fields(self, request: Any, obj: Any | None = ...) -> list[str] | tuple[Any, ...]:
        return list(super().get_readonly_fields(request, obj)) + (
            ['comment'] if obj and not obj.suggested_by == request.user else []
        )

    def save_form(self, request: Any, form: Any, change: bool) -> Any:
        new_object = super().save_form(request, form, change)
        if change:
            if 'status' in form.changed_data and request.user != new_object.suggested_by:
                match new_object.status:
                    case VariantSuggestion.Status.ACCEPTED:
                        launch_job_command(
                            command='notify',
                            user=request.user,
                            args=['variant_suggestion_accepted', str(new_object.id)],
                            allow_multiples=True,
                        )
                    case VariantSuggestion.Status.REJECTED:
                        launch_job_command(
                            command='notify',
                            user=request.user,
                            args=['variant_suggestion_rejected', str(new_object.id)],
                            allow_multiples=True,
                        )
        return new_object

    def save_model(self, request: Any, obj: Any, form: Any, change: bool):
        if not change:
            form.instance.suggested_by = request.user
        super().save_model(request, obj, form, change)
