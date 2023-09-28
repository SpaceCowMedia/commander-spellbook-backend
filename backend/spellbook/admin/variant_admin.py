from django.utils.http import urlencode
from django.utils.html import format_html
from django.urls import reverse, path
from django.db.models import Count, Prefetch
from django.forms import ModelForm
from django.http import HttpRequest
from django.shortcuts import redirect
from django.contrib import admin, messages
from spellbook.models import Card, Template, Feature, Variant, CardInVariant, TemplateInVariant
from spellbook.models.utils import recipe
from spellbook.utils import launch_job_command
from spellbook.parsers import variants_query_parser, NotSupportedError
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from .utils import IdentityFilter
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


class CardsCountListFilter(admin.SimpleListFilter):
    title = 'cards count'
    parameter_name = 'cards_count'
    one_more_than_max = DEFAULT_CARD_LIMIT + 1
    one_more_than_max_display = f'{one_more_than_max}+'

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(2, CardsCountListFilter.one_more_than_max)] + [(CardsCountListFilter.one_more_than_max_display, CardsCountListFilter.one_more_than_max_display)]

    def queryset(self, request, queryset):
        value = self.value()
        if value is not None:
            queryset = queryset.annotate(cards_count=Count('uses', distinct=True) + Count('requires', distinct=True))
            if value == CardsCountListFilter.one_more_than_max_display:
                return queryset.filter(cards_count__gte=CardsCountListFilter.one_more_than_max)
            value = int(value)
            return queryset.filter(cards_count=value)
        return queryset


@admin.action(description='Mark selected variants as RESTORE')
def set_restore(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.RESTORE)


@admin.action(description='Mark selected variants as DRAFT')
def set_draft(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.DRAFT)


@admin.action(description='Mark selected variants as NEW')
def set_new(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.NEW)


@admin.action(description='Mark selected variants as NOT WORKING')
def set_not_working(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.NOT_WORKING)


@admin.action(description='Mark selected variants as EXAMPLE')
def set_example(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.EXAMPLE)


class VariantForm(ModelForm):
    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    form = VariantForm
    readonly_fields = ['produces_link', 'of_link', 'includes_link', 'id', 'identity', 'legal', 'spoiler', 'scryfall_link']
    fieldsets = [
        ('Generated', {'fields': [
            'id',
            'produces_link',
            'of_link',
            'includes_link',
            'identity',
            'legal',
            'spoiler',
            'scryfall_link']}),
        ('Editable', {'fields': [
            'status',
            'mana_needed',
            'other_prerequisites',
            'description']})
    ]
    list_filter = ['status', CardsCountListFilter, IdentityFilter, 'legal', 'spoiler']
    list_display = ['display_name', 'status', 'identity']
    actions = [set_restore, set_draft, set_new, set_not_working, set_example]
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

    def display_name(self, obj):
        return recipe([card.name for card in obj.prefetched_uses] + [template.name for template in obj.prefetched_requires],
            [str(feature) for feature in obj.prefetched_produces])

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

    def get_queryset(self, request):
        return Variant.objects \
            .prefetch_related(
                Prefetch('uses', queryset=Card.objects.order_by('cardinvariant').only('name'), to_attr='prefetched_uses'),
                Prefetch('requires', queryset=Template.objects.order_by('templateinvariant').only('name'), to_attr='prefetched_requires'),
                Prefetch('produces', queryset=Feature.objects.only('name'), to_attr='prefetched_produces'))

    def get_search_results(self, request: HttpRequest, queryset, search_term: str) -> tuple[object, bool]:
        try:
            result = variants_query_parser(queryset, search_term)
            return result, False
        except NotSupportedError as e:
            messages.warning(request, str(e))
            return queryset, False
