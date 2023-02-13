from django.contrib import admin, messages
from django.urls import path
from .utils import launch_job_command
from .models import Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, CardInVariant, TemplateInVariant, Job
from django.contrib.admin.models import LogEntry, DELETION
from django.forms import ModelForm
from django.utils import timezone
from django.http import HttpRequest
from django.shortcuts import redirect
from django.db.models import Count
from .variants.combo_graph import MAX_CARDS_IN_COMBO
from django.urls import reverse
from django.utils.html import format_html
from .variants.variant_data import RestoreData
from .variants.variants_generator import restore_variant


# Admin configuration
admin.site.site_header = 'Spellbook Admin Panel'
admin.site.site_title = 'Spellbook Admin'
admin.site.index_title = 'Spellbook Admin Index'


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {'fields': ['oracle_id', 'identity', 'legal']}),
    ]
    # inlines = [FeatureInline]
    list_filter = ['identity', 'legal']
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'identity', 'id']


class CardInFeatureAdminInline(admin.StackedInline):
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
    inlines = [CardInFeatureAdminInline]
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


class ComboForm(ModelForm):
    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']


class IngredientInComboForm(ModelForm):
    def clean(self):
        if hasattr(self.cleaned_data['combo'], 'ingredient_count'):
            self.cleaned_data['combo'].ingredient_count += 1
        else:
            self.cleaned_data['combo'].ingredient_count = 1
        self.instance.order = self.cleaned_data['combo'].ingredient_count
        return super().clean()


class CardInComboAdminInline(admin.TabularInline):
    fields = ['card', 'zone_location', 'card_state']
    form = IngredientInComboForm
    model = CardInCombo
    extra = 0
    verbose_name = 'Card'
    verbose_name_plural = 'Required Cards'
    autocomplete_fields = ['card']
    max_num = MAX_CARDS_IN_COMBO


class TemplateInComboAdminInline(admin.TabularInline):
    fields = ['template', 'zone_location', 'card_state']
    form = IngredientInComboForm
    model = TemplateInCombo
    extra = 0
    verbose_name = 'Template'
    verbose_name_plural = 'Required Templates'
    autocomplete_fields = ['template']
    max_num = MAX_CARDS_IN_COMBO


class FeatureInComboAdminInline(admin.TabularInline):
    model = Combo.needs.through
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Required Features'
    autocomplete_fields = ['feature']
    max_num = MAX_CARDS_IN_COMBO


@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    form = ComboForm
    save_as = True
    readonly_fields = ['scryfall_link']
    fieldsets = [
        ('Generated', {'fields': ['scryfall_link']}),
        ('More Requirements', {'fields': [
            'mana_needed',
            'other_prerequisites']}),
        ('Features', {'fields': ['produces', 'removes']}),
        ('Description', {'fields': ['generator', 'description']}),
    ]
    inlines = [CardInComboAdminInline, TemplateInComboAdminInline, FeatureInComboAdminInline]
    filter_horizontal = ['uses', 'produces', 'needs', 'removes']
    list_filter = ['generator']
    search_fields = ['uses__name', 'requires__name', 'produces__name', 'needs__name']
    list_display = ['__str__', 'generator', 'id']

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('uses', 'requires', 'produces', 'needs', 'removes')

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if change:
            query = form.instance.variants.filter(status__in=[Variant.Status.NEW, Variant.Status.RESTORE])
            count = query.count()
            if count <= 0:
                return
            if count >= 1000:
                messages.warning(request, f'{count} "New" or "Restore" variants are too many to update for this combo: no automatic update was done.')
                return
            variants_to_update = list[Variant]()
            card_in_variants_to_update = list[CardInVariant]()
            template_in_variants_to_update = list[TemplateInVariant]()
            data = RestoreData()
            for variant in list[Variant](query):
                uses_set, requires_set = restore_variant(
                    variant,
                    list(variant.includes.all()),
                    list(variant.of.all()),
                    list(variant.cardinvariant_set.all()),
                    list(variant.templateinvariant_set.all()),
                    data=data)
                card_in_variants_to_update.extend(uses_set)
                template_in_variants_to_update.extend(requires_set)
            update_fields = ['status', 'mana_needed', 'other_prerequisites', 'description', 'legal', 'identity']
            Variant.objects.bulk_update(variants_to_update, update_fields)
            update_fields = ['zone_location', 'card_state', 'order']
            CardInVariant.objects.bulk_update(card_in_variants_to_update, update_fields)
            TemplateInVariant.objects.bulk_update(template_in_variants_to_update, update_fields)


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


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
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


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'action_time'
    list_filter = ['user', 'content_type', 'action_flag']
    search_fields = ['object_repr', 'change_message']
    list_display = ['action_time', 'user', 'content_type', 'object_link', 'action_flag']

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj=None) -> bool:
        return False

    @admin.display(ordering='object_repr', description='object')
    def object_link(self, obj: LogEntry) -> str:
        if obj.action_flag == DELETION:
            return format_html('{}', obj.object_repr)
        if obj.get_admin_url():
            return format_html('<a href="{}">{}</a>', obj.get_admin_url(), obj.object_repr)
        return format_html('{}', obj.object_repr)
