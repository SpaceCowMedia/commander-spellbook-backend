from typing import Any
from django.contrib import admin
from .utils import SpellbookAdminForm, SpellbookModelAdmin
from spellbook.models import Combo, VariantUpdateSuggestion, VariantInVariantUpdateSuggestion
from spellbook.utils import launch_job_command


class VariantInVariantUpdateSuggestionAdmin(admin.TabularInline):
    model = VariantInVariantUpdateSuggestion
    extra = 0
    verbose_name = 'variant in suggestion'
    verbose_name_plural = 'variants in suggestion'
    autocomplete_fields = ['variant']


class VariantUpdateSuggestionAdminForm(SpellbookAdminForm):
    def related_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            variants__variant_update_suggestions__suggestion=self.instance
        ).distinct().order_by('-created')


@admin.register(VariantUpdateSuggestion)
class VariantUpdateSuggestionAdmin(SpellbookModelAdmin):
    form = VariantUpdateSuggestionAdminForm
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
            'kind',
            'issue',
            'solution',
        ]}),
        ('Review', {'fields': [
            'status',
        ]}),
    ]
    inlines = [VariantInVariantUpdateSuggestionAdmin]
    list_filter = ['status', 'kind']
    list_display = ['__str__', 'kind', 'status', 'updated', 'suggested_by']
    search_fields = [
        '=pk',
        '=suggested_by__username',
        'issue',
        'solution',
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
                    case VariantUpdateSuggestion.Status.ACCEPTED:
                        launch_job_command(
                            command='notify',
                            user=request.user,
                            args=['variant_update_suggestion_accepted', str(new_object.id)],
                            allow_multiples=True,
                        )
                    case VariantUpdateSuggestion.Status.REJECTED:
                        launch_job_command(
                            command='notify',
                            user=request.user,
                            args=['variant_update_suggestion_rejected', str(new_object.id)],
                            allow_multiples=True,
                        )
        return new_object

    def save_model(self, request: Any, obj: Any, form: Any, change: bool):
        if not change:
            form.instance.suggested_by = request.user
        super().save_model(request, obj, form, change)
