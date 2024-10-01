from dataclasses import dataclass
import logging
from typing import Iterable
from multiset import FrozenMultiset
from django.conf import settings
from django.db import connection, reset_queries
from spellbook.models.card import Card, FeatureOfCard
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo, CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo
from spellbook.models.template import Template
from spellbook.models.variant import Variant, CardInVariant, TemplateInVariant, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo
from .variant_set import VariantSet


@dataclass(frozen=True)
class AttributesMatcher:
    any_of: frozenset[int]
    all_of: frozenset[int]
    none_of: frozenset[int]

    def matches(self, attributes: frozenset[int]) -> bool:
        return (not self.any_of or any(a in attributes for a in self.any_of)) \
            and (self.all_of <= attributes) \
            and not (self.none_of & attributes)


class Data:
    def __init__(self):
        # Features
        features = list(Feature.objects.all())
        # Cards
        cards = list(Card.objects.all())
        featureofcards = list(FeatureOfCard.objects.all())
        featureofcard_attributes = list(FeatureOfCard.attributes.through.objects.all())
        # Templates
        templates = list(Template.objects.all())
        # Combos
        combos = list(Combo.objects.filter(status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        cardincombos = list(CardInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        templateincombos = list(TemplateInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureproducedincombos = list(FeatureProducedInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureneededincombos = list(FeatureNeededInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureremovedincombos = list(FeatureRemovedInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureneededincombo_anyofattributes = list(FeatureNeededInCombo.any_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureneededincombo_allofattributes = list(FeatureNeededInCombo.all_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureneededincombo_noneofattributes = list(FeatureNeededInCombo.none_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        featureproducedincombo_attributes = list(FeatureProducedInCombo.attributes.through.objects.filter(featureproducedincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)))
        # Variants
        variants = list[Variant](Variant.objects.all())
        cardinvariants = list(CardInVariant.objects.all())
        templateinvariants = list(TemplateInVariant.objects.all())
        variantofcombos = list(VariantOfCombo.objects.all())
        variantincludescombos = list(VariantIncludesCombo.objects.all())
        featureproducedbyvariants = list(FeatureProducedByVariant.objects.all())
        # Data
        self.id_to_card = {c.id: c for c in cards}
        self.id_to_template = {t.id: t for t in templates}
        self.id_to_combo = {c.id: c for c in combos}
        self.id_to_variant = {v.id: v for v in variants}
        self.id_to_feature = {f.id: f for f in features}
        self.generator_combos = [c for c in combos if c.status == Combo.Status.GENERATOR]
        self.combo_to_cards = {c.id: list[CardInCombo]() for c in combos}
        for cardincombo in cardincombos:
            self.combo_to_cards[cardincombo.combo_id].append(cardincombo)
        for i in self.combo_to_cards.values():
            i.sort(key=lambda cic: cic.order)
        self.combo_to_templates = {c.id: list[TemplateInCombo]() for c in combos}
        for i in templateincombos:
            self.combo_to_templates[i.combo_id].append(i)
        for i in self.combo_to_templates.values():
            i.sort(key=lambda tic: tic.order)
        self.combo_to_produced_features = {c.id: list[FeatureProducedInCombo]() for c in combos}
        for i in featureproducedincombos:
            self.combo_to_produced_features[i.combo_id].append(i)
        self.combo_to_needed_features = {c.id: list[FeatureNeededInCombo]() for c in combos}
        for i in featureneededincombos:
            self.combo_to_needed_features[i.combo_id].append(i)
        self.combo_to_removed_features = {c.id: list[FeatureRemovedInCombo]() for c in combos}
        for i in featureremovedincombos:
            self.combo_to_removed_features[i.combo_id].append(i)

        self.feature_needed_in_combo_to_attributes_matcher = dict[int, AttributesMatcher]()
        feature_needed_in_combo_to_any_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_anyofattributes:
            feature_needed_in_combo_to_any_of_attributes[i.featureneededincombo_id].add(i.featureattribute_id)
        feature_needed_in_combo_to_all_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_allofattributes:
            feature_needed_in_combo_to_all_of_attributes[i.featureneededincombo_id].add(i.featureattribute_id)
        feature_needed_in_combo_to_none_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_noneofattributes:
            feature_needed_in_combo_to_none_of_attributes[i.featureneededincombo_id].add(i.featureattribute_id)
        for i in featureneededincombos:
            self.feature_needed_in_combo_to_attributes_matcher[i.id] = AttributesMatcher(
                any_of=frozenset(feature_needed_in_combo_to_any_of_attributes[i.id]),
                all_of=frozenset(feature_needed_in_combo_to_all_of_attributes[i.id]),
                none_of=frozenset(feature_needed_in_combo_to_none_of_attributes[i.id]),
            )
        self.feature_produced_in_combo_to_attributes = {f.id: set[int]() for f in featureproducedincombos}
        for i in featureproducedincombo_attributes:
            self.feature_produced_in_combo_to_attributes[i.featureproducedincombo_id].add(i.featureattribute_id)
        self.card_to_features = {c.id: list[FeatureOfCard]() for c in cards}
        self.features_to_cards = {f.id: list[FeatureOfCard]() for f in features}
        for i in featureofcards:
            self.card_to_features[i.card_id].append(i)
            self.features_to_cards[i.feature_id].append(i)
        self.feature_of_card_to_attributes = {f.id: set[int]() for f in featureofcards}
        for i in featureofcard_attributes:
            self.feature_of_card_to_attributes[i.featureofcard_id].add(i.featureattribute_id)

        self.variant_to_cards = {v.id: set[CardInVariant]() for v in variants}
        for i in cardinvariants:
            self.variant_to_cards[i.variant_id].add(i)
        self.variant_uses_card_dict = {(c.card_id, c.variant_id): c for c in cardinvariants}

        self.variant_to_templates = {v.id: set[TemplateInVariant]() for v in variants}
        for i in templateinvariants:
            self.variant_to_templates[i.variant_id].add(i)
        self.variant_requires_template_dict = {(t.template_id, t.variant_id): t for t in templateinvariants}

        self.variant_to_of_sets = {v.id: set[VariantOfCombo]() for v in variants}
        for i in variantofcombos:
            self.variant_to_of_sets[i.variant_id].add(i)
        self.variant_of_combo_dict = {(v.combo_id, v.variant_id): v for v in variantofcombos}

        self.variant_to_includes_sets = {v.id: set[VariantIncludesCombo]() for v in variants}
        for i in variantincludescombos:
            self.variant_to_includes_sets[i.variant_id].add(i)
        self.variant_includes_combo_dict = {(v.combo_id, v.variant_id): v for v in variantincludescombos}

        self.variant_to_produces = {v.id: set[FeatureProducedByVariant]() for v in variants}
        for i in featureproducedbyvariants:
            self.variant_to_produces[i.variant_id].add(i)
        self.variant_produces_feature_dict = {(f.feature_id, f.variant_id): f for f in featureproducedbyvariants}

        def fetch_not_working_variants(variants: Iterable[Variant]) -> VariantSet:
            variants = [v for v in variants if v.status == Variant.Status.NOT_WORKING]
            variant_set = VariantSet()
            for v in variants:
                variant_set.add(
                    FrozenMultiset({c.card_id: c.quantity for c in self.variant_to_cards[v.id]}),
                    FrozenMultiset({t.template_id: t.quantity for t in self.variant_to_templates[v.id]}),
                )
            return variant_set
        self.utility_features_ids = frozenset(f.id for f in self.id_to_feature.values() if f.utility)
        self.not_working_variants = fetch_not_working_variants(self.id_to_variant.values()).variants()


count = 0


def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
    return count
