from typing import Any
from django.db.models import Count, Prefetch
from django.forms import ModelForm, ValidationError
from django.forms.models import BaseInlineFormSet
from django.contrib import admin
from spellbook.models import Card, Template, Feature, VariantSuggestion, CardInVariantSuggestion, TemplateInVariantSuggestion, id_from_cards_and_templates_ids
from spellbook.models.utils import recipe
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from .utils import IdentityFilter
from .ingredient_admin import IngredientAdmin


class VariantSuggestionIngredientFormset(BaseInlineFormSet):
    def clean(self) -> None:
        super().clean()
        if any(self.errors):
            return
        # The following code is executed only if there are no errors in the formset
        # It exploits a trick to communicate with the parent form and the other formsets
        # It validates the uniqueness of the combination of cards and templates
        if hasattr(self.instance, '__templates__') and hasattr(self.instance, '__cards__'):
            self.instance.variant_id = id_from_cards_and_templates_ids(self.instance.__cards__, self.instance.__templates__)
            if VariantSuggestion.objects.filter(variant_id=self.instance.variant_id).exclude(pk=self.instance.pk).exists():
                self.instance.__parent_form__.add_error(None, ValidationError('This combination of cards was already suggested.'))
                raise ValidationError('')  # This is a hack to make the formset validation fail without displaying any error for this formset


class CardInVariantSuggestionFormset(VariantSuggestionIngredientFormset):
    def clean(self):
        cards_ids = [form.cleaned_data['card'].id for form in self.forms if form.cleaned_data['card']]
        self.instance.__cards__ = cards_ids
        super().clean()


class TemplateInVariantSuggestionFormset(VariantSuggestionIngredientFormset):
    def clean(self):
        templates_ids = [form.cleaned_data['template'].id for form in self.forms if form.cleaned_data['template']]
        self.instance.__templates__ = templates_ids
        super().clean()


class CardInVariantSuggestionAdminInline(IngredientAdmin):
    fields = ['card', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state']
    model = CardInVariantSuggestion
    formset = CardInVariantSuggestionFormset
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    autocomplete_fields = ['card']


class TemplateInVariantAdminInline(IngredientAdmin):
    fields = ['template', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state']
    model = TemplateInVariantSuggestion
    formset = TemplateInVariantSuggestionFormset
    verbose_name = 'Template'
    verbose_name_plural = 'Templates'
    autocomplete_fields = ['template']


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


@admin.action(description='Mark selected suggestions as REJECTED')
def set_rejected(modeladmin, request, queryset):
    queryset.update(status=VariantSuggestion.Status.REJECTED)


class VariantSuggestionForm(ModelForm):
    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']

    def clean(self):
        super().clean()
        self.instance.__parent_form__ = self


@admin.register(VariantSuggestion)
class VariantSuggestionAdmin(admin.ModelAdmin):
    form = VariantSuggestionForm
    save_as = True
    readonly_fields = ['id', 'variant_id', 'identity', 'legal', 'spoiler', 'scryfall_link', 'suggested_by']
    fieldsets = [
        ('Generated', {'fields': [
            'id',
            'variant_id',
            'suggested_by',
            'identity',
            'legal',
            'spoiler',
            'scryfall_link']}),
        ('Editable', {'fields': [
            'status',
            'produces',
            'mana_needed',
            'other_prerequisites',
            'description']})
    ]
    inlines = [CardInVariantSuggestionAdminInline, TemplateInVariantAdminInline]
    filter_horizontal = ['produces']
    list_filter = ['status', CardsCountListFilter, IdentityFilter, 'legal', 'spoiler']
    list_display = ['display_name', 'status', 'identity']
    actions = [set_rejected]

    def display_name(self, obj):
        return recipe([card.name for card in obj.prefetched_uses] + [template.name for template in obj.prefetched_requires],
            [str(feature) for feature in obj.prefetched_produces])

    def get_queryset(self, request):
        return VariantSuggestion.objects \
            .prefetch_related(
                Prefetch('uses', queryset=Card.objects.order_by('cardinvariantsuggestion').only('name'), to_attr='prefetched_uses'),
                Prefetch('requires', queryset=Template.objects.order_by('templateinvariantsuggestion').only('name'), to_attr='prefetched_requires'),
                Prefetch('produces', queryset=Feature.objects.only('name'), to_attr='prefetched_produces'))

    def save_model(self, request: Any, obj: Any, form: Any, change: Any) -> None:
        if not change:
            form.instance.suggested_by = request.user
        super().save_model(request, obj, form, change)
