import re
from typing import Any
from itertools import chain
from django.contrib import admin
from django.db.models import QuerySet, Count
from django.http import HttpRequest
from django.utils.html import format_html
from spellbook.models import CardInCombo, Feature, Combo, TemplateInCombo, batch_size_or_default
from spellbook.models.scryfall import scryfall_link_for_query, scryfall_query_string_for_card_names, SCRYFALL_MAX_QUERY_LENGTH
from spellbook.variants.variants_generator import FEATURE_REPLACEMENT_REGEX
from .utils import SpellbookModelAdmin, SpellbookAdminForm
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
    list_filter = ['status']

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

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
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
            new_name = instance.name
            if old_name and old_name != new_name:
                ingredient_fields = ['battlefield_card_state', 'exile_card_state', 'graveyard_card_state', 'library_card_state']
                cards_in_combos = list(CardInCombo.objects.filter(combo__needs=instance).only(*ingredient_fields).distinct())
                templates_in_combos = list(TemplateInCombo.objects.filter(combo__needs=instance).only(*ingredient_fields).distinct())
                for ingredient in chain(cards_in_combos, templates_in_combos):
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
                Combo.objects.bulk_update(combos, combo_fields, batch_size=batch_size_or_default())
                CardInCombo.objects.bulk_update(cards_in_combos, ingredient_fields, batch_size=batch_size_or_default())
                TemplateInCombo.objects.bulk_update(templates_in_combos, ingredient_fields, batch_size=batch_size_or_default())


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
