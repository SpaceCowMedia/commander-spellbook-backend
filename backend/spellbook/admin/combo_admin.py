import re
from django.db.models import Prefetch, Case, When, Count, Q
from django.forms import ModelForm
from django.contrib import admin, messages
from spellbook.models import Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, CardInVariant, TemplateInVariant
from spellbook.models.utils import recipe
from spellbook.variants.variant_data import RestoreData
from spellbook.variants.variants_generator import restore_variant
from .utils import SearchMultipleRelatedMixin, upper_oracle_symbols
from .ingredient_admin import IngredientAdmin


class ComboForm(ModelForm):
    def variants_for_editors(self):
        if self.instance.pk is None:
            return Variant.objects.none()
        return self.instance.variants.order_by(Case(
            When(status=Variant.Status.DRAFT, then=0),
            When(status=Variant.Status.NEW, then=1),
            default=2
        ), '-updated')

    def clean_mana_needed(self):
        if self.cleaned_data['mana_needed']:
            result = upper_oracle_symbols(self.cleaned_data['mana_needed'])
            return result
        return self.cleaned_data['mana_needed']


class CardInComboAdminInline(IngredientAdmin):
    fields = ['card', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander']
    model = CardInCombo
    verbose_name = 'Card'
    verbose_name_plural = 'Required Cards'
    autocomplete_fields = ['card']


class TemplateInComboAdminInline(IngredientAdmin):
    fields = ['template', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander']
    model = TemplateInCombo
    verbose_name = 'Template'
    verbose_name_plural = 'Required Templates'
    autocomplete_fields = ['template']


class FeatureInComboAdminInline(admin.TabularInline):
    model = Combo.needs.through
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Required Features'
    autocomplete_fields = ['feature']


class PayoffFilter(admin.SimpleListFilter):
    title = 'is payoff'
    parameter_name = 'payoff'

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        if self.value() == 'True':
            return queryset.filter(needs__utility=False).distinct()
        return queryset.exclude(needs__utility=False).distinct()


class VariantRelatedFilter(admin.SimpleListFilter):
    title = 'how is used by variants'
    parameter_name = 'in_variants'

    def lookups(self, request, model_admin):
        return [('unused', 'Unused'), ('overlapping', 'Overlapping'), ('redundant', 'Potentially redundant')]

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        if self.value() == 'unused':
            return queryset.filter(included_in_variants__isnull=True).distinct()
        elif self.value() == 'overlapping':
            return queryset.annotate(possible_overlaps=Count('variants__of', distinct=True)).filter(possible_overlaps__gt=1).distinct()
        elif self.value() == 'redundant':
            return queryset.annotate(possible_redundancies=Count('variants__includes', distinct=True, filter=Q(variants__generated_by__name='import_combos'))).filter(possible_redundancies__gt=1).distinct()


@admin.register(Combo)
class ComboAdmin(SearchMultipleRelatedMixin, admin.ModelAdmin):
    form = ComboForm
    save_as = True
    readonly_fields = ['scryfall_link']
    fieldsets = [
        ('Generated', {'fields': ['scryfall_link']}),
        ('More Requirements', {'fields': ['mana_needed', 'other_prerequisites']}),
        ('Results', {'fields': ['produces', 'removes']}),
        ('Description', {'fields': ['kind', 'description']}),
    ]
    inlines = [CardInComboAdminInline, FeatureInComboAdminInline, TemplateInComboAdminInline]
    filter_horizontal = ['uses', 'produces', 'needs', 'removes']
    list_filter = ['kind', PayoffFilter, VariantRelatedFilter]
    search_fields = ['uses__name', 'uses__name_unaccented', 'requires__name', 'produces__name', 'needs__name']
    list_display = ['display_name', 'kind', 'id']

    def display_name(self, obj):
        return recipe([card.name for card in obj.prefetched_uses] + [feature.name for feature in obj.prefetched_needs] + [template.name for template in obj.prefetched_requires],
            [feature.name for feature in obj.prefetched_produces])

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
            update_fields = ['status', 'mana_needed', 'other_prerequisites', 'description', 'identity']
            Variant.objects.bulk_update(variants_to_update, update_fields)
            update_fields = ['zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state', 'must_be_commander', 'order']
            CardInVariant.objects.bulk_update(card_in_variants_to_update, update_fields)
            TemplateInVariant.objects.bulk_update(template_in_variants_to_update, update_fields)
            messages.info(request, f'{count} "New" or "Restore" variants were updated for this combo.')

    def get_fieldsets(self, request, obj):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj or obj.uses.count() == 0:
            fieldsets = fieldsets[1:]
        return fieldsets

    def get_queryset(self, request):
        return Combo.objects \
            .prefetch_related(
                Prefetch('uses', queryset=Card.objects.order_by('cardincombo').only('name'), to_attr='prefetched_uses'),
                Prefetch('requires', queryset=Template.objects.order_by('templateincombo').only('name'), to_attr='prefetched_requires'),
                Prefetch('needs', queryset=Feature.objects.only('name'), to_attr='prefetched_needs'),
                Prefetch('produces', queryset=Feature.objects.only('name'), to_attr='prefetched_produces'))
