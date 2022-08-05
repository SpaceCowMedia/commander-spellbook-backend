from django.contrib import admin
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from .variants import check_combo_sanity
from .models import Card, Feature, Combo, Variant, Jobs
from django.contrib import messages
from django.forms import ModelForm
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Avg, F


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Spellbook', {'fields': ['name', 'features']}),
        ('Scryfall', {'fields': ['oracle_id']}),
    ]
    # inlines = [FeatureInline]
    search_fields = ['name', 'features__name']
    autocomplete_fields = ['features']
    list_display = ['name', 'id']


class CardInline(admin.StackedInline):
    model = Feature.cards.through
    extra = 1
    autocomplete_fields = ['card']
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    fieldsets = [
        (None, {'fields': ['name', 'description']}),
    ]
    inlines = [CardInline]
    search_fields = ['name', 'cards__name']
    list_display = ['name', 'id']


@admin.action(description='Mark selected variants as RESTORE')
def set_restore(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.RESTORE)


@admin.action(description='Mark selected variants as DRAFT')
def set_draft(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.DRAFT)


@admin.action(description='Mark selected variants as NEW')
def set_new(modeladmin, request, queryset):
    queryset.update(status=Variant.Status.NEW)


@admin.register(Variant)
class VariantAdmin(admin.ModelAdmin):
    readonly_fields = ['includes', 'produces', 'of', 'unique_id']
    fieldsets = [
        ('Generated', {'fields': ['unique_id', 'includes', 'produces', 'of']}),
        ('Editable', {'fields': ['status', 'prerequisites', 'description']})
    ]
    list_filter = ['status', 'produces__name']
    list_display = ['__str__', 'status', 'id']
    search_fields = ['id', 'includes__name', 'produces__name', 'unique_id']
    actions = [set_restore, set_draft, set_new]

    def generate(self, request):
        if request.method == 'POST' and request.user.is_authenticated:
            past_runs_duration = Jobs.objects \
                .filter(name='generate_variants', status=Jobs.Status.SUCCESS) \
                .order_by('-created') \
                [:5] \
                .annotate(duration=F('termination') - F('created')) \
                .aggregate(average_duration=Avg('duration'))['average_duration']
            if past_runs_duration is None:
                past_runs_duration = timezone.timedelta(minutes=30)

            job = Jobs.start(
                name='generate_variants',
                duration=past_runs_duration,
                user=request.user)
            if job is not None:
                import subprocess
                subprocess.Popen(['python', 'manage.py', 'generate_variants', '--id', str(job.id)])
                messages.info(request, 'Generation of variants job started.')
            else:
                messages.warning(request, 'Variant generation is already running.')
        return HttpResponseRedirect(reverse('admin:spellbook_variant_changelist'))

    def get_urls(self):
        return [path('generate/',
                    self.admin_site.admin_view(view=self.generate, cacheable=False),
                    name='spellbook_variant_generate')] + super().get_urls()

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ComboForm(ModelForm):
    def clean(self):
        if self.is_valid():
            if len(self.cleaned_data['includes']) + len(self.cleaned_data['needs']) == 0:
                raise ValidationError('Combo must include a card or need a feature to make sense.')
            ok = False
            with transaction.atomic(savepoint=True, durable=False):
                ok = check_combo_sanity(self.save(commit=True))
                transaction.set_rollback(True)
            if not ok:
                raise ValidationError('Possible loop detected.')
        return super().clean()


@admin.register(Combo)
class ComboAdmin(admin.ModelAdmin):
    form = ComboForm
    fieldsets = [
        ('Requirements', {'fields': ['includes', 'needs', 'prerequisites']}),
        ('Features', {'fields': ['produces', 'removes']}),
        ('Description', {'fields': ['generator', 'description']})
    ]
    filter_horizontal = ['includes', 'produces', 'needs', 'removes']
    list_filter = ['generator']
    search_fields = ['includes__name', 'produces__name', 'needs__name']
    list_display = ['__str__', 'generator', 'id']


@admin.register(Jobs)
class JobsAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'status', 'created', 'expected_termination', 'termination']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Admin configuration
admin.site.site_header = 'Spellbook Admin Panel'
admin.site.site_title = 'Spellbook Admin'
admin.site.index_title = 'Spellbook Admin Index'
