from typing import Any
from django.db.models.query import QuerySet
from django.utils.http import urlencode
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpRequest
from django.shortcuts import redirect
from django.contrib import admin, messages
from spellbook.models import Variant, CardInVariant, TemplateInVariant
from spellbook.utils import launch_job_command
from spellbook.parsers import variants_query_parser, NotSupportedError
from spellbook.serializers import VariantSerializer
from .utils import IdentityFilter, SpellbookModelAdmin, CardsCountListFilter
from .ingredient_admin import IngredientAdmin


class CardInVariantAdminInline(IngredientAdmin):
    readonly_fields = ['card_name']
    fields = ['card_name', *IngredientAdmin.fields]
    model = CardInVariant
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    can_delete = False

    def has_add_permission(self, request, obj) -> bool:
        return False

    def has_delete_permission(self, request, obj) -> bool:
        return False

    def card_name(self, instance):
        card = instance.card
        html = '<a href="{}" class="card-name">{}</a>'
        return format_html(html, reverse('admin:spellbook_card_change', args=(card.id,)), card.name)


class TemplateInVariantAdminInline(IngredientAdmin):
    readonly_fields = ['template']
    fields = ['template', *IngredientAdmin.fields]
    model = TemplateInVariant
    verbose_name = 'Template'
    verbose_name_plural = 'Templates'
    can_delete = False

    def has_add_permission(self, request, obj) -> bool:
        return False

    def has_delete_permission(self, request, obj) -> bool:
        return False


@admin.action(description='Mark selected variants as RESTORE')
def set_restore(modeladmin, request, queryset: QuerySet):
    count = queryset.update(status=Variant.Status.RESTORE)
    plural = 's' if count > 1 else ''
    messages.success(request, f'{count} variant{plural} marked as RESTORE.')


@admin.action(description='Mark selected variants as DRAFT')
def set_draft(modeladmin, request, queryset: QuerySet):
    count = queryset.update(status=Variant.Status.DRAFT)
    plural = 's' if count > 1 else ''
    messages.success(request, f'{count} variant{plural} marked as DRAFT.')


@admin.action(description='Mark selected variants as NEW')
def set_new(modeladmin, request, queryset: QuerySet):
    count = queryset.update(status=Variant.Status.NEW)
    plural = 's' if count > 1 else ''
    messages.success(request, f'{count} variant{plural} marked as NEW.')


@admin.action(description='Mark selected variants as NOT WORKING')
def set_not_working(modeladmin, request, queryset: QuerySet):
    count = queryset.update(status=Variant.Status.NOT_WORKING)
    plural = 's' if count > 1 else ''
    messages.success(request, f'{count} variant{plural} marked as NOT WORKING.')


@admin.action(description='Mark selected variants as EXAMPLE')
def set_example(modeladmin, request, queryset):
    # JSON preserialization has to be updated when the status becomes public.
    variants = list(VariantSerializer.prefetch_related(queryset))
    for variant in variants:
        variant.status = Variant.Status.EXAMPLE
    Variant.objects.bulk_serialize(variants, fields=['status'], serializer=VariantSerializer)  # type: ignore
    plural = 's' if len(variants) > 1 else ''
    messages.success(request, f'{len(variants)} variant{plural} marked as EXAMPLE.')


@admin.action(description='Mark selected variants as OK')
def set_ok(modeladmin, request, queryset):
    # JSON preserialization has to be updated when the status becomes public.
    variants = list(VariantSerializer.prefetch_related(queryset))
    for variant in variants:
        variant.status = Variant.Status.OK
    Variant.objects.bulk_serialize(variants, fields=['status'], serializer=VariantSerializer)  # type: ignore
    plural = 's' if len(variants) > 1 else ''
    messages.success(request, f'{len(variants)} variant{plural} marked as OK.')


@admin.register(Variant)
class VariantAdmin(SpellbookModelAdmin):
    generated_readonly_fields = [
        'id',
        'produces_link',
        'of_link',
        'includes_link',
        'identity',
        'spoiler',
        'scryfall_link',
        'spellbook_link',
        'popularity',
    ]
    readonly_fields = generated_readonly_fields + Variant.legalities_fields() + Variant.prices_fields()
    fieldsets = [
        ('Generated', {'fields': generated_readonly_fields}),
        ('Editable', {'fields': [
            'status',
            'mana_needed',
            'other_prerequisites',
            'description',
        ]}),
        ('Legalities', {
            'fields': Variant.legalities_fields(),
            'classes': ['collapse'],
            'description': 'Legalities are updated during generation.'
        }),
        ('Prices', {
            'fields': Variant.prices_fields(),
            'classes': ['collapse'],
            'description': 'Prices are updated during generation.'
        }),
    ]
    list_filter = ['status', CardsCountListFilter, IdentityFilter, 'legal_commander', 'spoiler']
    list_display = ['__str__', 'id', 'status', 'identity']
    actions = [set_restore, set_draft, set_new, set_not_working, set_example, set_ok]
    search_fields = ['id']

    @admin.display(description='produces')
    def produces_link(self, obj):
        features = list(obj.produces.all())
        format_for_each = '{}<br>'
        html = f'<a href="{{}}">{format_for_each * len(features)}</a>'
        return format_html(html, reverse('admin:spellbook_feature_changelist') + '?' + urlencode({'produced_by_variants__id': str(obj.id)}), *features)

    @admin.display(description='of')
    def of_link(self, obj):
        combos = list(obj.of.all())
        format_for_each = '{}<br>'
        html = f'<a href="{{}}">{format_for_each * len(combos)}</a>'
        return format_html(html, reverse('admin:spellbook_combo_changelist') + '?' + urlencode({'variants__id': str(obj.id)}), *combos)

    @admin.display(description='includes')
    def includes_link(self, obj):
        combos = list(obj.includes.all())
        format_for_each = '{}<br>'
        html = f'<a href="{{}}">{format_for_each * len(combos)}</a>'
        return format_html(html, reverse('admin:spellbook_combo_changelist') + '?' + urlencode({'included_in_variants__id': str(obj.id)}), *combos)

    def get_inlines(self, request, obj: Variant):
        inlines = []
        if obj is None or obj.id is None or obj.uses.exists():
            inlines.append(CardInVariantAdminInline)
        if obj is None or obj.id is None or obj.requires.exists():
            inlines.append(TemplateInVariantAdminInline)
        return inlines

    def generate(self, request: HttpRequest):
        if request.method == 'POST' and request.user.is_authenticated:
            if launch_job_command('generate_variants', request.user):
                messages.info(request, 'Variant generation job started.')
            else:
                messages.warning(request, 'Variant generation is already running.')
        return redirect('admin:spellbook_job_changelist')

    def export(self, request: HttpRequest):
        if request.method == 'POST' and request.user.is_authenticated:
            from ..management.s3_upload import can_upload_to_s3
            args = ['--s3'] if can_upload_to_s3() else []
            if launch_job_command('export_variants', request.user, args):
                messages.info(request, 'Variant exporting job started.')
            else:
                messages.warning(request, 'Variant exporting is already running.')
        return redirect('admin:spellbook_job_changelist')

    def get_urls(self):
        return [
            path('generate/',
                self.admin_site.admin_view(view=self.generate, cacheable=False),
                name='spellbook_variant_generate'),
            path('export/',
                self.admin_site.admin_view(view=self.export, cacheable=False),
                name='spellbook_variant_export')
        ] + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_search_results(self, request: HttpRequest, queryset, search_term: str) -> tuple[object, bool]:
        try:
            result = variants_query_parser(queryset, search_term)
            return result, False
        except NotSupportedError as e:
            messages.warning(request, str(e))
            return queryset, False

    def save_related(self, request: Any, form: Any, formsets: Any, change: Any):
        super().save_related(request, form, formsets, change)
        # Feature: update serialized JSON when variant is edited
        # effectively resulting in a real time update of the variant
        variant: Variant = form.instance
        variant.update_serialized(VariantSerializer)
        variant.save()

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'generated_by__id',
            'of__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)
