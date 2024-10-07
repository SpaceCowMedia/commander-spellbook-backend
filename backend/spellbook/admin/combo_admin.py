from typing import Any
from urllib.parse import urlencode
from django.contrib.admin.options import InlineModelAdmin
from django.db.models import Case, When, Count, Q
from django.contrib import admin, messages
from django.http.request import HttpRequest
from django.forms import Textarea
from django.utils.safestring import mark_safe
from django.urls import reverse, path
from django.shortcuts import redirect
from django.utils import timezone
from spellbook.utils import launch_job_command
from spellbook.models import Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion
from .utils import SpellbookModelAdmin, SpellbookAdminForm, CustomFilter, IngredientCountListFilter
from .ingredient_admin import IngredientInCombinationAdmin


def create_missing_object_message(url: str) -> str:
    return f'<a href="{url}" target="_blank"><u>Click here to add it</u></a>. Remember to refresh this page after adding the missing item.'


class ComboForm(SpellbookAdminForm):
    def variants_of_this(self):
        if self.instance.pk is None:
            return Variant.objects.none()
        return self.instance.variants.order_by(Case(
            When(status=Variant.Status.NEEDS_REVIEW, then=0),
            When(status=Variant.Status.DRAFT, then=1),
            When(status=Variant.Status.NEW, then=2),
            default=2
        ), '-updated')

    def variants_that_include_this(self):
        if self.instance.pk is None:
            return Variant.objects.none()
        return self.instance.included_in_variants.order_by(Case(
            When(status=Variant.Status.NEEDS_REVIEW, then=0),
            When(status=Variant.Status.DRAFT, then=1),
            When(status=Variant.Status.NEW, then=2),
            default=2
        ), '-updated')

    class Meta:
        widgets = {
            'notes': Textarea(attrs={'rows': 2}),
            'public_notes': Textarea(attrs={'rows': 2}),
        }


class CardInComboAdminInline(IngredientInCombinationAdmin):
    fields = ['card', *IngredientInCombinationAdmin.fields]
    model = CardInCombo
    verbose_name = 'Card'
    verbose_name_plural = 'Required Cards'
    autocomplete_fields = ['card']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        result = super().get_extra(request, obj, **kwargs)
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            result += len(request.from_suggestion.uses_dict)  # type: ignore
        return result


class TemplateInComboAdminInline(IngredientInCombinationAdmin):
    fields = ['template', *IngredientInCombinationAdmin.fields]
    model = TemplateInCombo
    verbose_name = 'Template'
    verbose_name_plural = 'Required Templates'
    autocomplete_fields = ['template']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        result = super().get_extra(request, obj, **kwargs)
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            result += len(request.from_suggestion.requires_dict)  # type: ignore
        return result


class FeatureNeededInComboAdminInline(admin.TabularInline):
    model = Combo.needs.through
    fields = ['feature', 'quantity', 'zone_locations_override', 'any_of_attributes', 'all_of_attributes', 'none_of_attributes']
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Required Features'
    autocomplete_fields = ['feature', 'any_of_attributes', 'all_of_attributes', 'none_of_attributes']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        result = super().get_extra(request, obj, **kwargs)
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            result += len(request.from_suggestion.needs_dict)  # type: ignore
        if hasattr(request, 'parent_feature') and request.parent_feature is not None:  # type: ignore
            result += 1
        if hasattr(request, 'child_feature') and request.child_feature is not None:  # type: ignore
            result += 1
        return result


class FeatureProducedInComboAdminInline(admin.TabularInline):
    model = Combo.produces.through
    fields = ['feature', 'attributes']
    extra = 0
    verbose_name = 'Feature'
    verbose_name_plural = 'Produced Features'
    autocomplete_fields = ['feature', 'attributes']

    def get_extra(self, request: HttpRequest, obj, **kwargs: Any) -> int:
        result = super().get_extra(request, obj, **kwargs)
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            result += len(request.from_suggestion.produces_dict)  # type: ignore
        if hasattr(request, 'parent_feature') and request.parent_feature is not None:  # type: ignore
            result += 1
        if hasattr(request, 'child_feature') and request.child_feature is not None:  # type: ignore
            result += 1
        return result


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
        return Q(
            pk__in=Combo.objects.alias(
                needs_utility_count=Count('needs', distinct=True, filter=Q(needs__utility=True)),
                needs_count=Count('needs', distinct=True),
                is_payoff=Q(needs_count__gt=0, needs_utility_count=0),
            ).filter(is_payoff=value),
        )


class VariantRelatedFilter(CustomFilter):
    title = 'how is used by variants'
    parameter_name = 'in_variants'

    def lookups(self, request, model_admin):
        return [('unused', 'Unused'), ('overlapping', 'Overlapping')]

    def filter(self, value: str) -> Q:
        match value:
            case 'unused':
                return Q(included_in_variants__isnull=True)
            case 'overlapping':
                return Q(
                    pk__in=Combo.objects.alias(
                        possible_overlaps=Count('variants__of', distinct=True),
                    ).filter(possible_overlaps__gt=1),
                )
        return Q()


@admin.register(Combo)
class ComboAdmin(SpellbookModelAdmin):
    form = ComboForm
    save_as = True
    readonly_fields = ['id', 'scryfall_link', 'updated', 'created']
    fieldsets = [
        ('Generated', {'fields': ['id', 'scryfall_link', 'updated', 'created']}),
        ('More Requirements', {'fields': ['mana_needed', 'other_prerequisites']}),
        ('Description', {'fields': ['status', 'allow_many_cards', 'allow_multiple_copies', 'description', 'public_notes', 'notes']}),
    ]
    inlines = [
        CardInComboAdminInline,
        FeatureNeededInComboAdminInline,
        TemplateInComboAdminInline,
        FeatureProducedInComboAdminInline,
        FeatureRemovedInComboAdminInline,
    ]
    list_filter = ['status', 'allow_many_cards', 'allow_multiple_copies', IngredientCountListFilter, PayoffFilter, VariantRelatedFilter]
    search_fields = [
        'uses__name',
        'uses__name_unaccented',
        'uses__name_unaccented_simplified',
        'uses__name_unaccented_simplified_with_spaces',
        'requires__name',
        'produces__name',
        'needs__name'
    ]
    list_display = ['name', 'id', 'status', 'allow_many_cards', 'allow_multiple_copies', 'updated']

    def get_fieldsets(self, request, obj):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj or obj.uses.count() == 0:
            fieldsets = fieldsets[1:]
        return fieldsets

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, str]:
        initial_data = super().get_changeform_initial_data(request)
        from_suggestion_id = request.GET.get('from_variant_suggestion', None)
        parent_feature = request.GET.get('parent_feature', None)
        child_feature = request.GET.get('child_feature', None)
        if from_suggestion_id:
            try:
                from_suggestion = VariantSuggestion.objects.get(pk=from_suggestion_id)
                request.from_suggestion = from_suggestion  # type: ignore
                initial_data['description'] = from_suggestion.description
                initial_data['mana_needed'] = from_suggestion.mana_needed
                initial_data['other_prerequisites'] = from_suggestion.other_prerequisites
                # Handle suggested produced features
                suggested_produced_features = list[str](from_suggestion.produces.values_list('feature', flat=True))
                found_produced_features = {f.name: f for f in Feature.objects.filter(name__in=suggested_produced_features)}
                for f in suggested_produced_features:
                    if f not in found_produced_features:
                        add_feature_link = reverse('admin:spellbook_feature_add') + '?' + urlencode({
                            'name': f,
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find produced feature "{f}" in database. {create_missing_object_message(add_feature_link)}'
                        ))
                request.from_suggestion.suggested_produced_features = suggested_produced_features  # type: ignore
                request.from_suggestion.produces_dict = found_produced_features  # type: ignore
                # Handle suggested used cards
                suggested_used_cards = list(from_suggestion.uses.all())
                found_used_cards = dict[str, Card]()
                for suggested_card in suggested_used_cards:
                    card_query = Q(name__iexact=suggested_card.card) \
                        | Q(name_unaccented__iexact=suggested_card.card) \
                        | Q(name_unaccented_simplified__iexact=suggested_card.card) \
                        | Q(name_unaccented_simplified_with_spaces__iexact=suggested_card.card)
                    query_result = list(Card.objects.filter(card_query)[:2])
                    if not query_result:
                        card_query = Q(name__icontains=suggested_card.card) \
                            | Q(name_unaccented__icontains=suggested_card.card) \
                            | Q(name_unaccented_simplified__icontains=suggested_card.card) \
                            | Q(name_unaccented_simplified_with_spaces__icontains=suggested_card.card)
                        query_result = list(Card.objects.filter(card_query)[:2])
                    if len(query_result) == 1:
                        found_used_cards[suggested_card.card] = query_result[0]
                    elif len(query_result) > 1:
                        picked = query_result[0]
                        messages.warning(request, f'Found multiple cards matching "{suggested_card.card}" in database. Check if {picked.name} is correct.')
                        found_used_cards[suggested_card.card] = picked
                    else:
                        add_card_link = reverse('admin:spellbook_card_add') + '?' + urlencode({
                            'name': suggested_card.card,
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find used card "{suggested_card.card}" in database. {create_missing_object_message(add_card_link)}'
                        ))
                request.from_suggestion.suggested_used_cards = suggested_used_cards  # type: ignore
                request.from_suggestion.uses_dict = found_used_cards  # type: ignore
                # Handle suggested required templates
                suggested_required_templates = list(from_suggestion.requires.all())
                found_required_templates: dict[str, Template] = {}
                found_needed_features: dict[str, Feature] = {}
                for suggested_template in suggested_required_templates:
                    t = Template.objects.filter(name__iexact=suggested_template.template).first()
                    if t:
                        found_required_templates[suggested_template.template] = t
                    f = Feature.objects.filter(name__iexact=suggested_template.template).first()
                    if f:
                        found_needed_features[suggested_template.template] = f
                    if not t and not f:
                        add_template_link = reverse('admin:spellbook_template_add') + '?' + urlencode({
                            'name': suggested_template.template,
                            'scryfall_query': suggested_template.scryfall_query or '',
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find required template "{suggested_template.template}" in database. {create_missing_object_message(add_template_link)}'
                        ))
                request.from_suggestion.suggested_required_templates = suggested_required_templates  # type: ignore
                request.from_suggestion.needs_dict = found_needed_features  # type: ignore
                request.from_suggestion.requires_dict = {template_name: found_required_templates[template_name] for template_name in found_required_templates.keys() - found_needed_features.keys()}  # type: ignore
            except VariantSuggestion.DoesNotExist:
                pass
        if parent_feature:
            try:
                feature = Feature.objects.get(pk=parent_feature)
                request.parent_feature = feature  # type: ignore
            except Feature.DoesNotExist:
                pass
        if child_feature:
            try:
                feature = Feature.objects.get(pk=child_feature)
                request.child_feature = feature  # type: ignore
            except Feature.DoesNotExist:
                pass
        return initial_data

    def get_formset_kwargs(self, request: HttpRequest, obj: Any, inline: InlineModelAdmin, prefix: str) -> dict[str, Any]:
        formset_kwargs = super().get_formset_kwargs(request, obj, inline, prefix)
        if not obj.id and hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            initial: list = formset_kwargs.setdefault('initial', [])
            if isinstance(inline, CardInComboAdminInline):
                suggestion_name_to_card_id: dict[str, Any] = {name: c.pk for name, c in request.from_suggestion.uses_dict.items()}  # type: ignore
                suggested_used_cards: list[CardUsedInVariantSuggestion] = request.from_suggestion.suggested_used_cards  # type: ignore
                for suggested_card in suggested_used_cards:
                    initial.append({
                        'card': suggestion_name_to_card_id.get(suggested_card.card, None),
                        'quantity': suggested_card.quantity,
                        'zone_locations': suggested_card.zone_locations,
                        'battlefield_card_state': suggested_card.battlefield_card_state,
                        'exile_card_state': suggested_card.exile_card_state,
                        'library_card_state': suggested_card.library_card_state,
                        'graveyard_card_state': suggested_card.graveyard_card_state,
                        'must_be_commander': suggested_card.must_be_commander,
                    })
            elif isinstance(inline, TemplateInComboAdminInline):
                suggestion_name_to_template_id: dict[str, Any] = {name: t.pk for name, t in request.from_suggestion.requires_dict.items()}  # type: ignore
                suggested_required_templates: list[TemplateRequiredInVariantSuggestion] = request.from_suggestion.suggested_required_templates  # type: ignore
                for suggested_template in suggested_required_templates:
                    if suggested_template.template in suggestion_name_to_template_id:
                        initial.append({
                            'template': suggestion_name_to_template_id[suggested_template.template],
                            'quantity': suggested_template.quantity,
                            'zone_locations': suggested_template.zone_locations,
                            'battlefield_card_state': suggested_template.battlefield_card_state,
                            'exile_card_state': suggested_template.exile_card_state,
                            'library_card_state': suggested_template.library_card_state,
                            'graveyard_card_state': suggested_template.graveyard_card_state,
                            'must_be_commander': suggested_template.must_be_commander,
                        })
            elif isinstance(inline, FeatureNeededInComboAdminInline):
                suggestion_name_to_feature_id: dict[str, Any] = {name: f.pk for name, f in request.from_suggestion.needs_dict.items()}  # type: ignore
                suggested_required_templates: list[TemplateRequiredInVariantSuggestion] = request.from_suggestion.suggested_required_templates  # type: ignore
                for suggested_template in suggested_required_templates:
                    if suggested_template.template in suggestion_name_to_feature_id:
                        initial.append({
                            'feature': suggestion_name_to_feature_id[suggested_template.template],
                            'quantity': suggested_template.quantity,
                        })
            elif isinstance(inline, FeatureProducedInComboAdminInline):
                suggestion_name_to_feature_id: dict[str, Any] = {name: f.pk for name, f in request.from_suggestion.produces_dict.items()}  # type: ignore
                suggested_produced_features: list[str] = request.from_suggestion.suggested_produced_features  # type: ignore
                for suggested_feature in suggested_produced_features:
                    if suggested_feature in suggestion_name_to_feature_id:
                        initial.append({
                            'feature': suggestion_name_to_feature_id[suggested_feature],
                        })
        if not obj.id and hasattr(request, 'parent_feature') and request.parent_feature is not None and isinstance(inline, FeatureNeededInComboAdminInline):  # type: ignore
            initial: list = formset_kwargs.setdefault('initial', [])
            initial.append({
                'feature': request.parent_feature.pk,  # type: ignore
            })
        if not obj.id and hasattr(request, 'child_feature') and request.child_feature is not None and isinstance(inline, FeatureProducedInComboAdminInline):  # type: ignore
            initial: list = formset_kwargs.setdefault('initial', [])
            initial.append({
                'feature': request.child_feature.pk,  # type: ignore
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
        duplicate_combos_query = Combo.objects.all()
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
            ).update(status=Variant.Status.RESTORE, updated=timezone.now())
            if updated:
                messages.info(request, f'Set {updated} "New" variants to "Restore" status.')

    def generate_variants(self, request: HttpRequest, id: int):
        if request.method == 'POST' and request.user.is_authenticated:
            if launch_job_command('generate_variants', request.user, args=['--combo', str(id)], group='single'):  # type: ignore
                messages.info(request, f'Variant generation job for combo {id} started.')
            else:
                messages.warning(request, 'Variant generation is already running.')
        return redirect('admin:spellbook_job_changelist')

    def get_urls(self):
        return [
            path(
                'generate-variants/<int:id>',
                self.admin_site.admin_view(view=self.generate_variants, cacheable=False),
                name='spellbook_combo_generate_variants'
            )
        ] + super().get_urls()
