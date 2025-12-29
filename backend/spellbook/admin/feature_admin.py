import re
from itertools import chain
from django.contrib import admin, messages
from django.db.models import QuerySet, Count, Q
from django.http import HttpRequest
from django.http.response import HttpResponse
from django.urls.resolvers import URLPattern
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from spellbook.models import CardInCombo, Feature, Combo, TemplateInCombo, DEFAULT_BATCH_SIZE, FeatureOfCard, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo, FeatureProducedByVariant
from spellbook.models.scryfall import scryfall_link_for_query, scryfall_query_string_for_card_names, SCRYFALL_MAX_QUERY_LENGTH
from spellbook.variants.variants_generator import FEATURE_REPLACEMENT_REGEX
from .utils import SpellbookModelAdmin, SpellbookAdminForm, CustomFilter
from .ingredient_admin import FeatureOfCardAdmin


class CardInFeatureAdminInline(FeatureOfCardAdmin):
    related_field = 'card'
    verbose_name = 'Produced by card'
    verbose_name_plural = 'Produced by cards'


class FeatureForm(SpellbookAdminForm):
    def child_feature_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.prefetch_related('produces').alias(
            produced_count=Count('produces', distinct=True),
            needed_count=Count('needs', distinct=True),
        ).filter(
            produced_count=1,
            needed_count=1,
            uses=None,
            requires=None,
            needs=self.instance,
        ).order_by('name')

    def parent_feature_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.prefetch_related('needs').alias(
            produced_count=Count('produces', distinct=True),
            needed_count=Count('needs', distinct=True),
        ).filter(
            produced_count=1,
            needed_count=1,
            uses=None,
            requires=None,
            produces=self.instance,
        ).order_by('name')

    def needed_by_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            needs=self.instance,
        ).exclude(
            pk__in=self.child_feature_combos(),
        )

    def produced_by_combos(self):
        if self.instance.pk is None:
            return Combo.objects.none()
        return Combo.objects.filter(
            produces=self.instance,
        ).exclude(
            pk__in=self.parent_feature_combos(),
        )


class ComboRelatedFilter(CustomFilter):
    title = 'how is used by combos'
    parameter_name = 'in_combos'

    def lookups(self, request, model_admin):
        return [
            ('unused', 'Unused'),
        ]

    def filter(self, value: str) -> Q:
        match value:
            case 'unused':
                return Q(
                    pk__in=Feature.objects.values('pk').filter(
                        needed_by_combos__isnull=True,
                        produced_by_combos__isnull=True,
                        removed_by_combos__isnull=True,
                    ),
                )
        return Q()


@admin.register(Feature)
class FeatureAdmin(SpellbookModelAdmin):
    form = FeatureForm
    readonly_fields = [
        'id',
        'scryfall_link',
        'updated',
        'created',
    ]
    fields = [
        'name',
        'id',
        'updated',
        'created',
        'status',
        'uncountable',
        'description',
        'scryfall_link',
    ]
    inlines = [CardInFeatureAdminInline]
    search_fields = [
        '=pk',
        'name',
        'cards__name',
    ]
    list_display = [
        'name',
        'id',
        'status',
        'produced_by_count',
        'updated',
    ]
    list_filter = ['status', 'uncountable', ComboRelatedFilter]

    def lookup_allowed(self, lookup: str, value: str, request) -> bool:
        if lookup in (
            'produced_by_variants__id',
        ):
            return True
        return super().lookup_allowed(lookup, value, request)  # type: ignore for deprecated typing

    @admin.display(description='Scryfall link')
    def scryfall_link(self, obj: Feature):
        card_names: list[str] = obj.cards.distinct().values_list('name', flat=True)  # type: ignore
        if card_names:
            query_string = scryfall_query_string_for_card_names(card_names)
            if len(query_string) <= SCRYFALL_MAX_QUERY_LENGTH:
                link = scryfall_link_for_query(query_string)
                plural = 's' if len(card_names) > 1 else ''
                return format_html('<a href="{}" target="_blank">Show card{} that produce this feature on scryfall</a>', link, plural)
            else:
                return 'Query too long for generating a scryfall link with all cards producing this feature'
        return None

    def get_queryset(self, request: HttpRequest) -> QuerySet[Feature]:
        return super().get_queryset(request).annotate(
            produced_by_count=Count('produced_by_variants', distinct=True) + Count('cards', distinct=True),
        ).order_by(*Feature._meta.ordering or [])

    @admin.display(description='Produced by variants or cards', ordering='produced_by_count')
    def produced_by_count(self, obj: Feature):
        if obj.pk is None:
            return 0
        return obj.produced_by_count  # type: ignore

    def after_save_related(self, request, form: FeatureForm, formsets, change):
        if change:
            old_name: str | None = form.initial.get('name')
            instance: Feature = form.instance
            if old_name is not None and old_name != instance.name:
                replace_feature_references(instance, old_name)
        super().after_save_related(request, form, formsets, change)

    def merge(self, request: HttpRequest, object_id: int):
        if request.method == 'POST' and request.user.is_authenticated:
            into_id = request.POST.get('into')
            if into_id is not None:
                if into_id == str(object_id):
                    messages.error(request, 'Cannot merge a feature into itself.')
                    return redirect('admin:spellbook_feature_change', object_id)
                try:
                    into_feature = Feature.objects.get(pk=into_id)
                    feature_to_merge = Feature.objects.get(pk=object_id)
                    return redirect(reverse('admin:spellbook_feature_delete', args=[feature_to_merge.pk]) + f'?merge_into={into_feature.pk}')
                except (Feature.DoesNotExist, ValueError):
                    messages.error(request, 'Invalid feature selected for merging.')
            else:
                messages.error(request, 'No feature selected for merging.')
        return redirect('admin:spellbook_feature_change', object_id)

    def delete_view(self, request: HttpRequest, object_id: str, extra_context=None) -> HttpResponse:
        merge_into = request.GET.get('merge_into')
        if merge_into is not None:
            try:
                into_feature = Feature.objects.get(pk=merge_into)
                extra_context = extra_context or {}
                extra_context['merge_into'] = into_feature  # type: ignore
                extra_context['title'] = f'Merge feature {object_id} into {into_feature.pk}'
            except (Feature.DoesNotExist, ValueError):
                pass
        return super().delete_view(request, object_id, extra_context)

    def delete_model(self, request: HttpRequest, obj: Feature):
        merge_into = request.POST.get('merge_into')
        if merge_into is not None:
            try:
                into_feature = Feature.objects.get(pk=merge_into)
                merge_feature(obj, into_feature)
                messages.success(request, f'Feature "{obj.name}" merged into "{into_feature.name}" successfully.')
            except (Feature.DoesNotExist, ValueError):
                messages.error(request, 'Invalid feature selected for merging. Deletion aborted.')
                return
        super().delete_model(request, obj)

    def get_urls(self) -> list[URLPattern]:
        return [
            path(
                '<path:object_id>/merge/',
                self.admin_site.admin_view(self.merge),
                name='spellbook_feature_merge',
            ),
            *super().get_urls(),
        ]


def merge_feature(from_obj: Feature, to_obj: Feature):
    FeatureOfCard.objects.filter(feature_id=from_obj.id, card__features=to_obj.id).delete()
    FeatureOfCard.objects.filter(feature_id=from_obj.id).update(feature_id=to_obj.id)
    FeatureNeededInCombo.objects.filter(feature_id=from_obj.id, combo__needs=to_obj.id).delete()
    FeatureNeededInCombo.objects.filter(feature_id=from_obj.id).update(feature_id=to_obj.id)
    FeatureProducedInCombo.objects.filter(feature_id=from_obj.id, combo__produces=to_obj.id).delete()
    FeatureProducedInCombo.objects.filter(feature_id=from_obj.id).update(feature_id=to_obj.id)
    FeatureRemovedInCombo.objects.filter(feature_id=from_obj.id, combo__removes=to_obj.id).delete()
    FeatureRemovedInCombo.objects.filter(feature_id=from_obj.id).update(feature_id=to_obj.id)
    FeatureProducedByVariant.objects.filter(feature_id=from_obj.id, variant__produces=to_obj.id).delete()
    FeatureProducedByVariant.objects.filter(feature_id=from_obj.id).update(feature_id=to_obj.id)
    replace_feature_references(to_obj, from_obj.name)


def replace_feature_references(instance: Feature, old_name: str):
    new_name = instance.name
    if old_name and old_name != new_name:
        ingredient_fields = ['battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state']
        cards_in_combos = list(CardInCombo.objects.filter(combo__needs=instance).only(*ingredient_fields).distinct())
        templates_in_combos = list(TemplateInCombo.objects.filter(combo__needs=instance).only(*ingredient_fields).distinct())
        features_in_combos = list(FeatureNeededInCombo.objects.filter(combo__needs=instance).only(*ingredient_fields).distinct())
        for ingredient in chain(cards_in_combos, templates_in_combos, features_in_combos):
            ingredient.battlefield_card_state = replace_feature_reference(old_name, new_name, ingredient.battlefield_card_state)
            ingredient.exile_card_state = replace_feature_reference(old_name, new_name, ingredient.exile_card_state)
            ingredient.graveyard_card_state = replace_feature_reference(old_name, new_name, ingredient.graveyard_card_state)
            ingredient.library_card_state = replace_feature_reference(old_name, new_name, ingredient.library_card_state)
        combo_fields = ['easy_prerequisites', 'notable_prerequisites', 'description', 'notes', 'comment']
        combos = list(Combo.objects.filter(needs=instance).only(*combo_fields).distinct())
        for combo in combos:
            combo.easy_prerequisites = replace_feature_reference(old_name, new_name, combo.easy_prerequisites)
            combo.notable_prerequisites = replace_feature_reference(old_name, new_name, combo.notable_prerequisites)
            combo.description = replace_feature_reference(old_name, new_name, combo.description)
            combo.notes = replace_feature_reference(old_name, new_name, combo.notes)
            combo.comment = replace_feature_reference(old_name, new_name, combo.comment)
        Combo.objects.bulk_update(combos, combo_fields, batch_size=DEFAULT_BATCH_SIZE)
        CardInCombo.objects.bulk_update(cards_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        TemplateInCombo.objects.bulk_update(templates_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)
        FeatureNeededInCombo.objects.bulk_update(features_in_combos, ingredient_fields, batch_size=DEFAULT_BATCH_SIZE)


def replace_feature_reference(old_name: str, new_name: str, text: str) -> str:
    def replacement_with_fallback(key: str, alias: str | None, selector: str | None, postfix_alias: str | None, otherwise: str) -> str:
        if key.lower() != old_name.lower():
            return otherwise
        result = new_name
        if alias is not None:
            result += f'|{alias}'
        if selector is not None:
            result += f'${selector}'
            if postfix_alias is not None:
                result += f'|{postfix_alias}'
        return f'[[{result}]]'
    return re.sub(
        FEATURE_REPLACEMENT_REGEX,
        lambda m: replacement_with_fallback(m.group('key'), m.group('alias'), m.group('selector'), m.group('postfix_alias'), m.group(0)),
        text,
        flags=re.IGNORECASE,
    )
