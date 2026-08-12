from django.contrib import admin
from django.db.models import QuerySet, Count, Q
from django.http import HttpRequest
from django.utils.html import format_html
from spellbook.models import Feature, Combo, FeatureOfCard, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo, FeatureProducedByVariant, replace_feature_references
from spellbook.models.scryfall import scryfall_link_for_query, scryfall_query_string_for_card_names, SCRYFALL_MAX_QUERY_LENGTH
from .utils import MergeableModelAdmin, SpellbookAdminForm, CustomFilter
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
class FeatureAdmin(MergeableModelAdmin):
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
        return super().lookup_allowed(lookup, value, request)  # type: ignore  # deprecated typing

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

    def merge_objects(self, from_obj: Feature, to_obj: Feature) -> None:
        merge_feature(from_obj, to_obj)


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
