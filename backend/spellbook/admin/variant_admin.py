from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.utils.http import urlencode
from django.utils.html import format_html
from django.urls import reverse, path
from django.http import HttpRequest
from django.shortcuts import redirect
from django.contrib import admin, messages
from django.forms import Textarea
from django.utils import timezone
from spellbook.models import Variant, CardInVariant, TemplateInVariant, DEFAULT_BATCH_SIZE
from spellbook.utils import launch_job_command
from spellbook.transformers.variants_query_transformer import variants_query_parser
from spellbook.serializers import VariantSerializer
from .utils import IdentityFilter, SpellbookModelAdmin, SpellbookAdminForm, CardCountListFilter
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


class VariantForm(SpellbookAdminForm):
    class Meta:
        widgets = {
            'notes': Textarea(attrs={'rows': 2}),
            'comment': Textarea(attrs={'rows': 2}),
        }


def set_status(request, queryset, status: Variant.Status):
    # JSON preserialization has to be updated when the status changes, in case it becomes public.
    variants = list(VariantSerializer.prefetch_related(queryset))
    unpublished = [variant for variant in variants if not variant.published]
    published = [variant for variant in variants if variant.published]
    publish = status in Variant.public_statuses()
    now = timezone.now()
    for variant in variants:
        variant.published = variant.published or publish
        variant.status = status
        variant.updated = now
    Variant.objects.bulk_serialize(variants, fields=['status', 'published', 'updated'], serializer=VariantSerializer, batch_size=DEFAULT_BATCH_SIZE)
    plural = 's' if len(variants) > 1 else ''
    messages.success(request, f'{len(variants)} variant{plural} marked as {status.name}.')
    if publish:
        if unpublished:
            launch_job_command(
                command='notify',
                user=request.user,
                args=['variant_published', *[str(variant.id) for variant in unpublished]],
                allow_multiples=True,
            )
        if published:
            launch_job_command(
                command='notify',
                user=request.user,
                args=['variant_updated', *[str(variant.id) for variant in published]],
                allow_multiples=True,
            )


@admin.action(description='Mark selected variants as RESTORE')
def set_restore(modeladmin, request, queryset: QuerySet):
    set_status(request, queryset, Variant.Status.RESTORE)


@admin.action(description='Mark selected variants as DRAFT')
def set_draft(modeladmin, request, queryset: QuerySet):
    set_status(request, queryset, Variant.Status.DRAFT)


@admin.action(description='Mark selected variants as NEEDS REVIEW')
def set_needs_review(modeladmin, request, queryset: QuerySet):
    set_status(request, queryset, Variant.Status.NEEDS_REVIEW)


@admin.action(description='Mark selected variants as NEW')
def set_new(modeladmin, request, queryset: QuerySet):
    set_status(request, queryset, Variant.Status.NEW)


@admin.action(description='Mark selected variants as NOT WORKING')
def set_not_working(modeladmin, request, queryset: QuerySet):
    set_status(request, queryset, Variant.Status.NOT_WORKING)


@admin.action(description='Mark selected variants as EXAMPLE')
def set_example(modeladmin, request, queryset):
    set_status(request, queryset, Variant.Status.EXAMPLE)


@admin.action(description='Mark selected variants as OK')
def set_ok(modeladmin, request, queryset):
    set_status(request, queryset, Variant.Status.OK)


@admin.register(Variant)
class VariantAdmin(SpellbookModelAdmin):
    form = VariantForm
    generated_readonly_fields = [
        'id',
        'updated',
        'created',
        'produces_link',
        'of_link',
        'includes_link',
        'identity',
        'spoiler',
        'scryfall_link',
        'spellbook_link',
        'popularity',
        'hulkline',
    ]
    readonly_fields = generated_readonly_fields + Variant.computed_fields()
    fieldsets = [
        ('Generated', {'fields': generated_readonly_fields}),
        ('Editable', {'fields': [
            'status',
            'mana_needed',
            'easy_prerequisites',
            'notable_prerequisites',
            'description',
            'notes',
            'comment',
        ]}),
        ('Bracket', {
            'fields': ['bracket_tag', 'bracket_tag_override'],
            'classes': ['collapse'],
            'description': 'Bracket-related data for this variant.',
        }),
        ('Legalities', {
            'fields': Variant.legalities_fields(),
            'classes': ['collapse'],
            'description': 'Legalities are updated during generation.',
        }),
        ('Prices', {
            'fields': Variant.prices_fields(),
            'classes': ['collapse'],
            'description': 'Prices are updated during generation.',
        }),
    ]
    list_filter = ['status', CardCountListFilter, IdentityFilter, 'legal_commander', 'spoiler']
    list_display = ['name', 'id', 'status', 'identity', 'updated']
    actions = [set_restore, set_draft, set_new, set_needs_review, set_not_working, set_example, set_ok]
    search_fields = ['id']
    search_help_text = 'You can search variants using the usual Commander Spellbook query syntax.'

    @admin.display(description='produces')
    def produces_link(self, obj: Variant):
        features = [
            (f'{produced.quantity}x ' if produced.quantity > 1 else '') + produced.feature.name
            for produced
            in obj.featureproducedbyvariant_set.all()
        ]
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
            job = launch_job_command('generate_variants', request.user, group='all')  # type: ignore
            if job is not None:
                messages.info(request, 'Variant generation job started.')
                return redirect('admin:spellbook_job_change', job.id)
            else:
                messages.warning(request, 'Variant generation is already running.')
        return redirect('admin:spellbook_variant_changelist')

    def export(self, request: HttpRequest):
        if request.method == 'POST' and request.user.is_authenticated:
            from ..management.s3_upload import can_upload_to_s3
            args = ['--s3'] if can_upload_to_s3() else []
            job = launch_job_command('export_variants', request.user, args)  # type: ignore
            if job is not None:
                messages.info(request, 'Variant exporting job started.')
                return redirect('admin:spellbook_job_change', job.id)
            else:
                messages.warning(request, 'Variant exporting is already running.')
        return redirect('admin:spellbook_variant_changelist')

    def get_urls(self):
        return [
            path(
                'generate/',
                self.admin_site.admin_view(view=self.generate, cacheable=False),
                name='spellbook_variant_generate',
            ),
            path(
                'export/',
                self.admin_site.admin_view(view=self.export, cacheable=False),
                name='spellbook_variant_export',
            ),
        ] + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_search_results(self, request: HttpRequest, queryset, search_term: str) -> tuple[object, bool]:
        try:
            result = variants_query_parser(queryset, search_term)
            return result, False
        except ValidationError as e:
            for message in e.messages:
                messages.warning(request, message)
            return queryset, False

    def after_save_related(self, request, form, formsets, change):
        variant: Variant = form.instance
        if change and 'status' in form.changed_data:
            if variant.status in Variant.public_statuses():
                if variant.published:
                    launch_job_command(
                        command='notify',
                        user=request.user,  # type: ignore
                        args=['variant_updated', str(variant.id)],
                        allow_multiples=True,
                    )
                else:
                    variant.published = True
                    launch_job_command(
                        command='notify',
                        user=request.user,  # type: ignore
                        args=['variant_published', str(variant.id)],
                        allow_multiples=True,
                    )
        # Feature: update serialized JSON when variant is edited
        # effectively resulting in a real time update of the variant
        variant.update_serialized(VariantSerializer)
        variant.save()

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'generated_by__id',
            'of__id',
            'includes__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)  # type: ignore for deprecated typing
