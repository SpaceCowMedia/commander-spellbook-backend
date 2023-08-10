from django.db.models import Count, Prefetch
from django.forms import ModelForm
from django.contrib import admin
from spellbook.models import Card, Template, Feature, VariantSuggestion, CardInVariantSuggestion, TemplateInVariantSuggestion
from spellbook.models.utils import recipe
from spellbook.variants.variants_generator import DEFAULT_CARD_LIMIT
from .utils import IdentityFilter
from .ingredient_admin import IngredientAdmin


class CardInVariantSuggestionAdminInline(IngredientAdmin):
    fields = ['card', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state']
    model = CardInVariantSuggestion
    verbose_name = 'Card'
    verbose_name_plural = 'Cards'
    autocomplete_fields = ['card']


class TemplateInVariantAdminInline(IngredientAdmin):
    fields = ['template', 'zone_locations', 'battlefield_card_state', 'exile_card_state', 'library_card_state', 'graveyard_card_state']
    model = TemplateInVariantSuggestion
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
        if self.value() is not None:
            queryset = queryset.annotate(cards_count=Count('uses', distinct=True) + Count('requires', distinct=True))
            if self.value() == CardsCountListFilter.one_more_than_max_display:
                return queryset.filter(cards_count__gte=CardsCountListFilter.one_more_than_max)
            value = int(self.value())
            return queryset.filter(cards_count=value)
        return queryset


@admin.action(description='Mark selected suggestions as REJECTED')
def set_rejected(modeladmin, request, queryset):
    queryset.update(status=VariantSuggestion.Status.REJECTED)


class VariantSuggestionForm(ModelForm):
    def clean_mana_needed(self):
        return self.cleaned_data['mana_needed'].upper() if self.cleaned_data['mana_needed'] else self.cleaned_data['mana_needed']


@admin.register(VariantSuggestion)
class VariantSuggestionAdmin(admin.ModelAdmin):
    form = VariantSuggestionForm
    readonly_fields = ['id', 'identity', 'legal', 'spoiler', 'scryfall_link', 'suggested_by']
    fieldsets = [
        ('Generated', {'fields': [
            'id',
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
    search_fields = ['id']
    actions = [set_rejected]

    def display_name(self, obj):
        return recipe([card.name for card in obj.prefetched_uses] + [template.name for template in obj.prefetched_requires],
            [str(feature) for feature in obj.prefetched_produces])

    def get_queryset(self, request):
        return VariantSuggestion.objects \
            .prefetch_related(
                Prefetch('uses', queryset=Card.objects.order_by('cardinvariant').only('name'), to_attr='prefetched_uses'),
                Prefetch('requires', queryset=Template.objects.order_by('templateinvariant').only('name'), to_attr='prefetched_requires'),
                Prefetch('produces', queryset=Feature.objects.only('name'), to_attr='prefetched_produces'))
