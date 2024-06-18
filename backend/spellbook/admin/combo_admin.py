from typing import Any
from urllib.parse import urlencode
from django.contrib.admin.options import InlineModelAdmin
from django.db.models import Case, When, Count, Q
from django.contrib import admin, messages
from django.http.request import HttpRequest
from django.forms import Textarea
from django.utils.safestring import mark_safe
from django.urls import reverse
from spellbook.models import Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion
from .utils import SpellbookModelAdmin, SpellbookAdminForm, CustomFilter
from .ingredient_admin import IngredientInCombinationAdmin


def create_missing_object_message(url: str) -> str:
    return f'<a href="{url}" target="_blank"><u>Click here to add it</u></a>. Remember to refresh this page after adding the missing item.'


class ComboForm(SpellbookAdminForm):
    def variants_for_editors(self):
        if self.instance.pk is None:
            return Variant.objects.none()
        return self.instance.variants.order_by(Case(
            When(status=Variant.Status.NEEDS_REVIEW, then=0),
            When(status=Variant.Status.DRAFT, then=1),
            When(status=Variant.Status.NEW, then=2),
            default=2
        ), '-updated')

    class Meta:
        widgets = {
            'notes': Textarea(attrs={'rows': 2}),
        }


class CardInComboAdminInline(IngredientInCombinationAdmin):
    fields = ['card', *IngredientInCombinationAdmin.fields]
    model = CardInCombo
    verbose_name = 'Card'
    verbose_name_plural = 'Required Cards'
    autocomplete_fields = ['card']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            return len(request.from_suggestion.uses_list)  # type: ignore
        return super().get_extra(request, obj, **kwargs)


class TemplateInComboAdminInline(IngredientInCombinationAdmin):
    fields = ['template', *IngredientInCombinationAdmin.fields]
    model = TemplateInCombo
    verbose_name = 'Template'
    verbose_name_plural = 'Required Templates'
    autocomplete_fields = ['template']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            return len(request.from_suggestion.requires_list)  # type: ignore
        return super().get_extra(request, obj, **kwargs)


class FeatureNeededInComboAdminInline(admin.TabularInline):
    model = Combo.needs.through
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Required Features'
    autocomplete_fields = ['feature']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            return len(request.from_suggestion.needs_list)  # type: ignore
        return super().get_extra(request, obj, **kwargs)


class FeatureProducedInComboAdminInline(admin.TabularInline):
    model = Combo.produces.through
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Produced Features'
    autocomplete_fields = ['feature']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            return len(request.from_suggestion.produces_list)  # type: ignore
        return super().get_extra(request, obj, **kwargs)


class FeatureRemovedInComboAdminInline(admin.TabularInline):
    model = Combo.removes.through
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Removed Features'
    autocomplete_fields = ['feature']
    classes = ['collapse']


class PayoffFilter(CustomFilter):
    title = 'is payoff'
    parameter_name = 'payoff'
    data_type = bool

    def lookups(self, request, model_admin):
        return [(True, 'Yes'), (False, 'No')]

    def filter(self, value: data_type) -> Q:
        return Q(is_payoff=value)


class VariantRelatedFilter(CustomFilter):
    title = 'how is used by variants'
    parameter_name = 'in_variants'

    def lookups(self, request, model_admin):
        return [('unused', 'Unused'), ('overlapping', 'Overlapping'), ('redundant', 'Potentially redundant')]

    def filter(self, value: str) -> Q:
        match value:
            case 'unused':
                return Q(included_in_variants__isnull=True)
            case 'overlapping':
                return Q(possible_overlaps__gt=1)
            case 'redundant':
                return Q(possible_redundancies__gt=1)
        return Q()


@admin.register(Combo)
class ComboAdmin(SpellbookModelAdmin):
    form = ComboForm
    save_as = True
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fieldsets = [
        ('Generated', {'fields': ['id', 'scryfall_link', 'updated', 'created']}),
        ('More Requirements', {'fields': ['mana_needed', 'other_prerequisites']}),
        ('Description', {'fields': ['status', 'allow_many_cards', 'allow_multiple_copies', 'description', 'notes']}),
    ]
    inlines = [
        CardInComboAdminInline,
        FeatureNeededInComboAdminInline,
        TemplateInComboAdminInline,
        FeatureProducedInComboAdminInline,
        FeatureRemovedInComboAdminInline,
    ]
    list_filter = ['status', 'allow_many_cards', 'allow_multiple_copies', PayoffFilter, VariantRelatedFilter]
    search_fields = [
        'uses__name',
        'uses__name_unaccented',
        'uses__name_unaccented_simplified',
        'uses__name_unaccented_simplified_with_spaces',
        'requires__name',
        'produces__name',
        'needs__name'
    ]
    list_display = ['__str__', 'id', 'status', 'allow_many_cards', 'allow_multiple_copies', 'updated']

    def get_fieldsets(self, request, obj):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj or obj.uses.count() == 0:
            fieldsets = fieldsets[1:]
        return fieldsets

    def get_queryset(self, request):
        return Combo.objects.alias(
            needs_utility_count=Count('needs', distinct=True, filter=Q(needs__utility=True)),
            needs_count=Count('needs', distinct=True),
            is_payoff=Q(needs_count__gt=0, needs_utility_count=0),
            possible_overlaps=Count('variants__of', distinct=True),
            possible_redundancies=Count('variants__includes', distinct=True, filter=Q(variants__generated_by__name='import_combos')))

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, str]:
        initial_data = super().get_changeform_initial_data(request)
        from_suggestion_id = request.GET.get('from_variant_suggestion', None)
        if from_suggestion_id:
            try:
                from_suggestion = VariantSuggestion.objects.get(pk=from_suggestion_id)
                request.from_suggestion = from_suggestion  # type: ignore
                initial_data['description'] = from_suggestion.description
                initial_data['mana_needed'] = from_suggestion.mana_needed
                initial_data['other_prerequisites'] = from_suggestion.other_prerequisites
                suggested_produced_features = list(from_suggestion.produces.values_list('feature', flat=True))
                found_produced_features = list(Feature.objects.filter(name__in=suggested_produced_features))
                found_produced_features_names = {f.name for f in found_produced_features}
                for f in suggested_produced_features:
                    if f not in found_produced_features_names:
                        add_feature_link = reverse('admin:spellbook_feature_add') + '?' + urlencode({
                            'name': f,
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find produced feature "{f}" in database. {create_missing_object_message(add_feature_link)}'
                        ))
                request.from_suggestion.produces_list = found_produced_features  # type: ignore
                request.from_suggestion.uses_list = list(from_suggestion.uses.all())  # type: ignore
                suggested_required_templates: list[TemplateRequiredInVariantSuggestion] = list(from_suggestion.requires.all())
                suggested_template_names = [suggested_template.template for suggested_template in suggested_required_templates]
                found_required_templates = list(Template.objects.filter(name__in=suggested_template_names))
                found_required_templates_names = {t.name for t in found_required_templates}
                found_needed_features = list(Feature.objects.filter(name__in=suggested_template_names))
                found_needed_features_names = {f.name for f in found_needed_features}
                for suggested_template in suggested_required_templates:
                    if suggested_template.template not in found_required_templates_names and suggested_template.template not in found_needed_features_names:
                        add_template_link = reverse('admin:spellbook_template_add') + '?' + urlencode({
                            'name': suggested_template.template,
                            'scryfall_query': suggested_template.scryfall_query or '',
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find required template "{suggested_template.template}" in database. {create_missing_object_message(add_template_link)}'
                        ))
                request.from_suggestion.suggested_required_templates = suggested_required_templates  # type: ignore
                request.from_suggestion.needs_list = found_needed_features  # type: ignore
                request.from_suggestion.requires_list = [template for template in found_required_templates if template.name not in found_needed_features_names]  # type: ignore
            except VariantSuggestion.DoesNotExist:
                pass
        return initial_data

    def get_formset_kwargs(self, request: HttpRequest, obj: Any, inline: InlineModelAdmin, prefix: str) -> dict[str, Any]:
        formset_kwargs = super().get_formset_kwargs(request, obj, inline, prefix)
        if not obj.id and hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            if isinstance(inline, CardInComboAdminInline):
                formset_kwargs['initial'] = []
                suggested_used_cards: list[CardUsedInVariantSuggestion] = request.from_suggestion.uses_list  # type: ignore
                found_used_cards_names_to_id = dict[str, str]()
                for suggested_card in suggested_used_cards:
                    card_query = Q(name__iexact=suggested_card.card) \
                        | Q(name_unaccented__iexact=suggested_card.card) \
                        | Q(name_unaccented_simplified__iexact=suggested_card.card) \
                        | Q(name_unaccented_simplified_with_spaces__iexact=suggested_card.card)
                    query_result = Card.objects.filter(card_query)
                    if query_result.count() == 0:
                        card_query = Q(name__icontains=suggested_card.card) \
                            | Q(name_unaccented__icontains=suggested_card.card) \
                            | Q(name_unaccented_simplified__icontains=suggested_card.card) \
                            | Q(name_unaccented_simplified_with_spaces__icontains=suggested_card.card)
                        query_result = Card.objects.filter(card_query)
                    if query_result.count() == 1:
                        found_used_cards_names_to_id[suggested_card.card] = query_result.first().pk  # type: ignore
                    elif query_result.count() > 1:
                        picked: Card = query_result.first()  # type: ignore
                        messages.warning(request, f'Found multiple cards matching "{suggested_card.card}" in database. Check if {picked.name} is correct.')
                        found_used_cards_names_to_id[suggested_card.card] = picked.pk
                    else:
                        add_card_link = reverse('admin:spellbook_card_add') + '?' + urlencode({
                            'name': suggested_card.card,
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find used card "{suggested_card.card}" in database. {create_missing_object_message(add_card_link)}'
                        ))
                for suggested_card in suggested_used_cards:
                    formset_kwargs['initial'].append({
                        'card': found_used_cards_names_to_id.get(suggested_card.card, None),
                        'quantity': suggested_card.quantity,
                        'zone_locations': suggested_card.zone_locations,
                        'battlefield_card_state': suggested_card.battlefield_card_state,
                        'exile_card_state': suggested_card.exile_card_state,
                        'library_card_state': suggested_card.library_card_state,
                        'graveyard_card_state': suggested_card.graveyard_card_state,
                        'must_be_commander': suggested_card.must_be_commander,
                    })
            elif isinstance(inline, TemplateInComboAdminInline):
                formset_kwargs['initial'] = []
                found_required_templates_names_to_id = {t.name: t.pk for t in request.from_suggestion.requires_list}  # type: ignore
                suggested_required_templates: list[TemplateRequiredInVariantSuggestion] = request.from_suggestion.suggested_required_templates  # type: ignore
                for suggested_template in suggested_required_templates:
                    if suggested_template.template in found_required_templates_names_to_id:
                        formset_kwargs['initial'].append({
                            'template': found_required_templates_names_to_id[suggested_template.template],
                            'quantity': suggested_template.quantity,
                            'zone_locations': suggested_template.zone_locations,
                            'battlefield_card_state': suggested_template.battlefield_card_state,
                            'exile_card_state': suggested_template.exile_card_state,
                            'library_card_state': suggested_template.library_card_state,
                            'graveyard_card_state': suggested_template.graveyard_card_state,
                            'must_be_commander': suggested_template.must_be_commander,
                        })
            elif isinstance(inline, FeatureNeededInComboAdminInline):
                formset_kwargs['initial'] = []
                found_needed_features_ids = {f.pk for f in request.from_suggestion.needs_list}  # type: ignore
                for feature_id in found_needed_features_ids:
                    formset_kwargs['initial'].append({
                        'feature': feature_id,
                    })
            elif isinstance(inline, FeatureProducedInComboAdminInline):
                formset_kwargs['initial'] = []
                found_produced_features_ids = {f.pk for f in request.from_suggestion.produces_list}  # type: ignore
                for feature_id in found_produced_features_ids:
                    formset_kwargs['initial'].append({
                        'feature': feature_id,
                    })
        return formset_kwargs

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'variants__id',
            'included_in_variants__id',
            'uses__id',
            'requires__id',
            'produces__id',
            'needs__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)  # type: ignore for deprecated typing

    def after_save_related(self, request, form, formsets, change):
        instance: Combo = form.instance
        duplicate_combos_query = Combo.objects
        card_ids = list(instance.uses.values_list('id', flat=True))
        template_ids = list(instance.requires.values_list('id', flat=True))
        feature_ids = list(instance.needs.values_list('id', flat=True))
        for card_id in card_ids:
            duplicate_combos_query = duplicate_combos_query.filter(uses=card_id)
        for template_id in template_ids:
            duplicate_combos_query = duplicate_combos_query.filter(requires=template_id)
        for feature_id in feature_ids:
            duplicate_combos_query = duplicate_combos_query.filter(needs=feature_id)
        duplicate_combos_query = Combo.objects.filter(id__in=duplicate_combos_query).annotate(
            uses_count=Count('uses', distinct=True),
            requires_count=Count('requires', distinct=True),
            needs_count=Count('needs', distinct=True),
        ).filter(
            uses_count=len(card_ids),
            requires_count=len(template_ids),
            needs_count=len(feature_ids),
        )
        duplicate_combos = list(duplicate_combos_query.exclude(pk=instance.pk).values_list('id', flat=True))
        if duplicate_combos:
            message = f'This combo is a duplicate of {len(duplicate_combos)} other combos, with ids: '
            message += ', '.join(str(c) for c in duplicate_combos[:10])
            if len(duplicate_combos) > 10:
                message += '...'
            messages.warning(request, message)
        if change:
            # Set all new variants to restore
            updated = Variant.objects.filter(
                of=instance,
                status=Variant.Status.NEW
            ).update(status=Variant.Status.RESTORE)
            if updated:
                messages.info(request, f'Set {updated} "New" variants to "Restore" status.')
