from django.contrib import admin
from django.urls import path
from .utils import launch_job_command
from .models import Card, Template, Feature, Combo, Variant, Job
from django.contrib import messages
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.http import HttpRequest
from django.shortcuts import redirect
from django.db.models import Count
from .variants.combo_graph import MAX_CARDS_IN_COMBO


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {'fields': ['oracle_id', 'identity']}),
    ]
    # inlines = [FeatureInline]
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']


class CardInline(admin.StackedInline):
    model = Feature.cards.through
    extra = 1
    autocomplete_fields = ['card']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'utility', 'description']}),
    ]
    inlines = [CardInline]
    search_fields = ['name', 'cards__name']
    list_display = ['name', 'utility', 'id']
    list_filter = ['utility']


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


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    form = VariantForm
    readonly_fields = ['uses', 'requires', 'produces', 'of', 'includes', 'unique_id', 'identity']
    fieldsets = [
        ('Generated', {'fields': ['unique_id', 'uses', 'requires', 'produces', 'of', 'includes', 'identity']}),
        ('Editable', {'fields': [
            'status',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites',
            'description',
            'frozen']})
    ]
    list_filter = ['status', CardsCountListFilter, 'identity']
    list_display = ['__str__', 'status', 'id', 'identity']
    search_fields = ['id', 'uses__name', 'produces__name', 'requires__name', 'unique_id', 'identity']
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


class ComboForm(ModelForm):
    def clean(self):
        if self.is_valid():
            if len(self.cleaned_data['uses']) + len(self.cleaned_data['needs']) == 0:
                raise ValidationError('Combo must include a card or need a feature to make sense.')
        return super().clean()

    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']


@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    form = ComboForm
    fieldsets = [
        ('Requirements', {'fields': [
            'uses',
            'needs',
            'requires',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites']}),
        ('Features', {'fields': ['produces', 'removes']}),
        ('Description', {'fields': ['generator', 'description']}),
    ]
    filter_horizontal = ['uses', 'requires', 'produces', 'needs', 'removes']
    list_filter = ['generator']
    search_fields = ['uses__name', 'requires__name', 'produces__name', 'needs__name']
    list_display = ['__str__', 'generator', 'id']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('uses', 'requires', 'produces', 'needs', 'removes')


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    fields = ['id', 'name', 'status', 'created', 'expected_termination', 'termination', 'message', 'started_by']
    list_display = ['id', 'name', 'status', 'created', 'expected_termination', 'termination']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    readonly_fields = ['scryfall_link']
    fields = ['name', 'scryfall_query', 'scryfall_link']
    list_display = ['name', 'scryfall_query', 'id']
    search_fields = ['name', 'scryfall_query']


# Admin configuration
admin.site.site_header = 'Spellbook Admin Panel'
admin.site.site_title = 'Spellbook Admin'
admin.site.index_title = 'Spellbook Admin Index'
