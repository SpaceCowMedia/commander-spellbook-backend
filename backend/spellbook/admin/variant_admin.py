from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse, path
from django.db.models import Count
from django.forms import ModelForm
from django.http import HttpRequest
from django.shortcuts import redirect
from django.utils import timezone
from ..models import Variant, CardInVariant, TemplateInVariant
from ..variants.combo_graph import MAX_CARDS_IN_COMBO
from ..utils import launch_job_command
from .mixins import SearchMultipleRelatedMixin


class CardInVariantAdminInline(admin.TabularInline):
    readonly_fields = ['card_name']
    fields = ['card_name', 'zone_location', 'card_state']
    model = CardInVariant
    extra = 0
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


class TemplateInVariantAdminInline(admin.TabularInline):
    readonly_fields = ['template']
    fields = ['template', 'zone_location', 'card_state']
    model = TemplateInVariant
    extra = 0
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

    def lookups(self, request, model_admin):
        return [(i, str(i)) for i in range(2, MAX_CARDS_IN_COMBO + 1)]

    def queryset(self, request, queryset):
        if self.value() is not None:
            value = int(self.value())
            return queryset.annotate(cards_count=Count('uses', distinct=True) + Count('requires', distinct=True)).filter(cards_count=value)
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


class VariantForm(ModelForm):
    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']


@admin.register(Variant)
class VariantAdmin(SearchMultipleRelatedMixin, admin.ModelAdmin):
    form = VariantForm
    inlines = [CardInVariantAdminInline, TemplateInVariantAdminInline]
    readonly_fields = ['produces', 'of', 'includes', 'unique_id', 'identity', 'legal', 'scryfall_link']
    fieldsets = [
        ('Generated', {'fields': [
            'unique_id',
            'produces',
            'of',
            'includes',
            'identity',
            'legal',
            'scryfall_link']}),
        ('Editable', {'fields': [
            'status',
            'mana_needed',
            'other_prerequisites',
            'description',
            'frozen']})
    ]
    list_filter = ['status', CardsCountListFilter, 'identity', 'legal']
    list_display = ['__str__', 'status', 'id', 'identity']
    search_fields = ['=id', 'uses__name', 'produces__name', 'requires__name', '=unique_id']
    actions = [set_restore, set_draft, set_new, set_not_working]

    def generate(self, request: HttpRequest):
        if request.method == 'POST' and request.user.is_authenticated:
            if (launch_job_command('generate_variants', timezone.timedelta(minutes=30), request.user)):
                messages.info(request, 'Variant generation job started.')
            else:
                messages.warning(request, 'Variant generation is already running.')
        return redirect('admin:spellbook_job_changelist')

    def export(self, request: HttpRequest):
        if request.method == 'POST' and request.user.is_authenticated:
            if (launch_job_command('export_variants', timezone.timedelta(minutes=1), request.user)):
                messages.info(request, 'Variant exporting job started.')
            else:
                messages.warning(request, 'Variant exporting is already running.')
        return redirect('admin:spellbook_job_changelist')

    def get_urls(self):
        return [path('generate/',
                    self.admin_site.admin_view(view=self.generate, cacheable=False),
                    name='spellbook_variant_generate'),
                path('export/',
                    self.admin_site.admin_view(view=self.export, cacheable=False),
                    name='spellbook_variant_export')] + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request) \
            .prefetch_related('uses', 'requires', 'produces', 'of', 'includes')
