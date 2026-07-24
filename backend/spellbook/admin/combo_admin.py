from collections import defaultdict
from typing import Any
from urllib.parse import urlencode
from django.contrib.admin.options import InlineModelAdmin
from django.db.models import Case, Sum, When, Count, Q
from django.contrib import admin, messages
from django.db.models.functions import Coalesce
from django.forms.models import BaseModelFormSet
from django.http.request import HttpRequest
from django.forms import Textarea
from django.template.response import TemplateResponse
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString, mark_safe
from django.urls import reverse, path
from django.shortcuts import redirect
from django.utils import timezone
from django.tasks import TaskResult
from spellbook.models import Card, FeatureNeededInCombo, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion
from spellbook.tasks import generate_variants_task
from .utils import SpellbookModelAdmin, SpellbookAdminForm, CustomFilter, IngredientCountListFilter
from .ingredient_admin import IngredientAdmin, IngredientInCombinationAdmin


DUPLICATE_CONFIRMATION_INPUT_NAME = '_confirm_duplicate'
DUPLICATE_CANCELLATION_INPUT_NAME = '_cancel_duplicate'
DUPLICATE_COMBOS_DISPLAY_LIMIT = 10


def create_missing_object_message(url: str) -> str:
    return f'<a href="{url}" target="_blank"><u>Click here to add it</u></a>. Remember to refresh this page after adding the missing item.'


def find_duplicate_combos(
    cards: dict[int, int],
    templates: dict[int, int],
    features_needed: dict[int, int],
    excluded_combo_id: int | None = None,
) -> list[int]:
    '''Find the ids of the combos requiring exactly the given cards, templates and features, in the given quantities.'''
    duplicate_combos_query = Combo.objects.all()
    cards_query = Combo.objects.all()
    for card_id, quantity in cards.items():
        cards_query = cards_query.alias(matched_cards=Sum('cardincombo__quantity', filter=Q(cardincombo__card_id=card_id))).filter(matched_cards=quantity)
    duplicate_combos_query = duplicate_combos_query.filter(pk__in=cards_query)
    templates_query = Combo.objects.all()
    for template_id, quantity in templates.items():
        templates_query = templates_query.alias(matched_templates=Sum('templateincombo__quantity', filter=Q(templateincombo__template_id=template_id))).filter(matched_templates=quantity)
    duplicate_combos_query = duplicate_combos_query.filter(pk__in=templates_query)
    features_query = Combo.objects.all()
    for feature_id, quantity in features_needed.items():
        features_query = features_query.alias(features=Sum('featureneededincombo__quantity', filter=Q(featureneededincombo__feature_id=feature_id))).filter(features=quantity)
    duplicate_combos_query = duplicate_combos_query.filter(pk__in=features_query)
    for quantity_field, expected_total in (
        ('cardincombo__quantity', sum(cards.values())),
        ('templateincombo__quantity', sum(templates.values())),
        ('featureneededincombo__quantity', sum(features_needed.values())),
    ):
        duplicate_combos_query = duplicate_combos_query.filter(pk__in=duplicate_combos_query.alias(total=Coalesce(Sum(quantity_field), 0)).filter(total=expected_total))
    if excluded_combo_id is not None:
        duplicate_combos_query = duplicate_combos_query.exclude(pk=excluded_combo_id)
    return list(duplicate_combos_query.values_list('id', flat=True))


def submitted_quantities(formset: BaseModelFormSet | None, related_field_name: str) -> dict[int, int] | None:
    '''Sum the submitted quantities by related object id, or None if the submitted data can't be interpreted.'''
    if formset is None or not formset.is_valid():
        return None
    quantity_by_id = defaultdict[int, int](int)
    for form_data in formset.cleaned_data:
        if not form_data or form_data.get('DELETE'):
            continue
        related_object = form_data.get(related_field_name)
        if related_object is None:
            continue
        quantity_by_id[related_object.pk] += form_data.get('quantity') or 1
    return quantity_by_id


def duplicate_combos_links(duplicate_combo_ids: list[int]) -> SafeString:
    links = format_html_join(
        ', ',
        '<a href="{}" target="_blank">{}</a>',
        (
            (reverse('admin:spellbook_combo_change', args=[combo_id]), combo_id)
            for combo_id in duplicate_combo_ids[:DUPLICATE_COMBOS_DISPLAY_LIMIT]
        ),
    )
    if len(duplicate_combo_ids) > DUPLICATE_COMBOS_DISPLAY_LIMIT:
        links += mark_safe('...')
    return links


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
            'comment': Textarea(attrs={'rows': 2}),
        }


class CardInComboAdminInline(IngredientInCombinationAdmin):
    fields = ['card', IngredientInCombinationAdmin.fields[0], 'used_face', *IngredientInCombinationAdmin.fields[1:]]  # pyright: ignore[reportGeneralTypeIssues]
    model = CardInCombo
    verbose_name = 'Card'
    verbose_name_plural = 'Required Cards'
    autocomplete_fields = ['card']

    def get_extra(self, request: HttpRequest, obj: Combo | None = None, **kwargs: Any) -> int:
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

    def get_extra(self, request: HttpRequest, obj: Combo | None = None, **kwargs: Any) -> int:
        result = super().get_extra(request, obj, **kwargs)
        if hasattr(request, 'from_suggestion') and request.from_suggestion is not None:  # type: ignore
            result += len(request.from_suggestion.requires_dict)  # type: ignore
        return result


class FeatureNeededInComboAdminInline(IngredientAdmin):
    fields = [
        'feature',
        *IngredientAdmin.fields,
        'any_of_attributes',
        'all_of_attributes',
        'none_of_attributes',
    ]
    model = FeatureNeededInCombo
    verbose_name = 'Feature'
    verbose_name_plural = 'Required Features'
    autocomplete_fields = ['feature', 'any_of_attributes', 'all_of_attributes', 'none_of_attributes']

    def get_extra(self, request: HttpRequest, obj: Combo | None = None, **kwargs: Any) -> int:
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

    def get_extra(self, request: HttpRequest, obj: Combo | None = None, **kwargs: Any) -> int:
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

    def filter(self, value: bool) -> Q:
        return Q(
            pk__in=Combo.objects.alias(
                needs_utility_count=Count('needs', distinct=True, filter=Q(needs__status__in=(Feature.Status.HIDDEN_UTILITY, Feature.Status.PUBLIC_UTILITY))),
                needs_count=Count('needs', distinct=True),
                is_payoff=Q(needs_count__gt=0, needs_utility_count=0),
            ).filter(is_payoff=value),
        )


class VariantRelatedFilter(CustomFilter):
    title = 'how is used by variants'
    parameter_name = 'in_variants'

    def lookups(self, request, model_admin):
        return [
            ('unused', 'Unused'),
            ('overlapping', 'Overlapping'),
        ]

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
        ('More Requirements', {'fields': [('mana_needed', 'is_mana_needed_an_accurate_minimum'), 'easy_prerequisites', 'notable_prerequisites']}),
        ('Description', {'fields': ['status', 'allow_many_cards', 'allow_multiple_copies', 'description', 'notes', 'comment']}),
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
        '=pk',
        'uses__name',
        'uses__name_unaccented',
        'uses__name_unaccented_simplified',
        'uses__name_unaccented_simplified_with_spaces',
        'requires__name',
        'produces__name',
        'needs__name'
    ]
    list_display = ['name', 'id', 'status', 'allow_many_cards', 'allow_multiple_copies', 'updated', 'variant_count']

    def get_inline_formsets(self, request, formsets, inline_instances, obj=None, **kwargs):
        inline_admin_formsets = super().get_inline_formsets(request, formsets, inline_instances, obj=obj, **kwargs)
        for inline_admin_formset in inline_admin_formsets:
            classes: list[str] = inline_admin_formset.classes.split()
            if 'collapse' in classes:
                if isinstance(inline_admin_formset.opts, FeatureRemovedInComboAdminInline):
                    if obj and obj.removes.exists():
                        classes.remove('collapse')
            inline_admin_formset.classes = ' '.join(classes)
        return inline_admin_formsets

    def get_fieldsets(self, request, obj):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj or not obj.uses.exists():
            fieldsets = fieldsets[1:]
        return fieldsets

    def get_changeform_initial_data(self, request: HttpRequest) -> dict[str, str | list[str]]:
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
                initial_data['easy_prerequisites'] = from_suggestion.easy_prerequisites
                initial_data['notable_prerequisites'] = from_suggestion.notable_prerequisites
                # Handle suggested produced features
                suggested_produced_features = list[str](from_suggestion.produces.values_list('feature', flat=True))
                found_produced_features = {f.name: f for f in Feature.objects.filter(name__in=suggested_produced_features)}
                for feature_name in suggested_produced_features:
                    if feature_name not in found_produced_features:
                        add_feature_link = reverse('admin:spellbook_feature_add') + '?' + urlencode({
                            'name': feature_name,
                            'status': Feature.Status.HELPER,
                        })
                        messages.warning(request, mark_safe(
                            f'Could not find produced feature "{feature_name}" in database. {create_missing_object_message(add_feature_link)}'
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
            initial = formset_kwargs.setdefault('initial', [])
            initial.append({
                'feature': request.parent_feature.pk,  # type: ignore
            })
        if not obj.id and hasattr(request, 'child_feature') and request.child_feature is not None and isinstance(inline, FeatureProducedInComboAdminInline):  # type: ignore
            initial = formset_kwargs.setdefault('initial', [])
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
        return super().lookup_allowed(lookup, value, request)  # type: ignore  # deprecated typing

    def _create_formsets(self, request: HttpRequest, obj, change: bool):
        formsets, inline_instances = super()._create_formsets(request, obj, change)  # type: ignore  # private method
        if request.method == 'POST' and DUPLICATE_CONFIRMATION_INPUT_NAME not in request.POST:
            self.reject_duplicate_combo(request, obj, formsets)
        return formsets, inline_instances

    def reject_duplicate_combo(self, request: HttpRequest, obj: Combo | None, formsets: list[BaseModelFormSet]):
        '''
        Look for combos with the same requirements as the submitted one, before it gets saved.
        When some are found the submitted data is rejected, so that the editor can either confirm
        the duplicate on the confirmation page, or go back to the form and change the combo.
        '''
        formsets_by_model = {formset.model: formset for formset in formsets}
        cards = submitted_quantities(formsets_by_model.get(CardInCombo), 'card')
        templates = submitted_quantities(formsets_by_model.get(TemplateInCombo), 'template')
        features_needed = submitted_quantities(formsets_by_model.get(FeatureNeededInCombo), 'feature')
        if cards is None or templates is None or features_needed is None:
            return  # the submitted data has errors of its own, and is going to be shown back to the editor anyway
        duplicate_combos = find_duplicate_combos(
            cards=cards,
            templates=templates,
            features_needed=features_needed,
            excluded_combo_id=obj.pk if obj is not None else None,
        )
        if not duplicate_combos:
            return
        formsets_by_model[CardInCombo].non_form_errors().append(format_html(
            'This combo was not saved, because it has the same used cards, required templates and needed features as {} other {}, with ids: {}.'
            ' Change them to make this combo unique, or save it again and confirm to have a duplicate anyway.',
            len(duplicate_combos),
            'combo' if len(duplicate_combos) == 1 else 'combos',
            duplicate_combos_links(duplicate_combos),
        ))
        if DUPLICATE_CANCELLATION_INPUT_NAME not in request.POST:
            request.duplicate_combos_to_confirm = duplicate_combos  # type: ignore

    def _changeform_view(self, request: HttpRequest, object_id, form_url, extra_context):
        response = super()._changeform_view(request, object_id, form_url, extra_context)  # type: ignore  # private method
        duplicate_combos: list[int] | None = getattr(request, 'duplicate_combos_to_confirm', None)
        if duplicate_combos:
            if request.method == 'POST' and '_saveasnew' in request.POST:
                object_id = None  # saving as new adds a combo, like the add form does
            return self.render_duplicate_confirmation(request, object_id, duplicate_combos)
        return response

    def render_duplicate_confirmation(self, request: HttpRequest, object_id, duplicate_combos: list[int]) -> TemplateResponse:
        opts = self.model._meta
        return TemplateResponse(request, 'admin/spellbook/combo/duplicate_confirmation.html', {
            **self.admin_site.each_context(request),
            'title': 'Are you sure?',
            'subtitle': None,
            'opts': opts,
            'object_id': object_id,
            'add': object_id is None,
            'duplicate_combos': Combo.objects.filter(pk__in=duplicate_combos[:DUPLICATE_COMBOS_DISPLAY_LIMIT]),
            'duplicate_combo_count': len(duplicate_combos),
            'preserved_form_data': [
                (name, value)
                for name, values in request.POST.lists()
                for value in values
                if name != 'csrfmiddlewaretoken'
            ],
            'confirmation_input_name': DUPLICATE_CONFIRMATION_INPUT_NAME,
            'cancellation_input_name': DUPLICATE_CANCELLATION_INPUT_NAME,
        })

    def after_save_related(self, request, form, formsets, change):
        instance: Combo = form.instance
        if change:
            # Set all new variants to restore
            updated = Variant.objects.filter(
                of=instance,
                status=Variant.Status.NEW
            ).update(status=Variant.Status.RESTORE, updated=timezone.now())
            if updated:
                messages.info(request, f'Set {updated} "New" variants to "Restore" status.')

    def generate_variants(self, request: HttpRequest, object_id: str):
        if request.method == 'POST' and request.user.is_authenticated:
            combo = Combo.objects.filter(pk=object_id).first()
            if not combo:
                messages.error(request, f'Combo with id {object_id} does not exist.')
                return redirect('admin:spellbook_combo_changelist')
            if combo.status == Combo.Status.GENERATOR:
                result: TaskResult = generate_variants_task.enqueue(combo=int(object_id), started_by_user_id=request.user.pk)
                messages.info(request, f'Enqueued variant generation task for combo {object_id}.')
                return redirect('admin:django_tasks_database_dbtaskresult_change', result.id)
            else:
                messages.error(request, f'Combo with id {object_id} is not marked as a generator combo.')
        return redirect('admin:spellbook_combo_change', object_id)

    def get_urls(self):
        return [
            path(
                '<path:object_id>/generate-variants/',
                self.admin_site.admin_view(view=self.generate_variants, cacheable=False),
                name='spellbook_combo_generate_variants',
            ),
            *super().get_urls(),
        ]
