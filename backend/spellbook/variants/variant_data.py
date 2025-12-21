from dataclasses import dataclass
import logging
from django.conf import settings
from django.db import connection, reset_queries
from spellbook.models.card import Card, FeatureOfCard
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo, CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo
from spellbook.models.template import Template
from spellbook.models.variant import Variant, CardInVariant, TemplateInVariant, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo


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
        features = list(Feature.objects.order_by())
        # Cards
        cards = list(Card.objects.order_by())
        featureofcards = list(FeatureOfCard.objects.order_by())
        featureofcard_attributes = list(FeatureOfCard.attributes.through.objects.order_by())
        # Templates
        templates = list(Template.objects.order_by())
        # Combos
        combos = list(Combo.objects.order_by())  # Draft combos are only used to update the variant count
        cardincombos = list(CardInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        templateincombos = list(TemplateInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureproducedincombos = list(FeatureProducedInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureneededincombos = list(FeatureNeededInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureremovedincombos = list(FeatureRemovedInCombo.objects.filter(combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureneededincombo_anyofattributes = list(FeatureNeededInCombo.any_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureneededincombo_allofattributes = list(FeatureNeededInCombo.all_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureneededincombo_noneofattributes = list(FeatureNeededInCombo.none_of_attributes.through.objects.filter(featureneededincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        featureproducedincombo_attributes = list(FeatureProducedInCombo.attributes.through.objects.filter(featureproducedincombo__combo__status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).order_by())
        # Variants
        variants = list[Variant](Variant.objects.order_by())
        cardinvariants = list(CardInVariant.objects.order_by())
        templateinvariants = list(TemplateInVariant.objects.order_by())
        variantofcombos = list(VariantOfCombo.objects.order_by())
        variantincludescombos = list(VariantIncludesCombo.objects.order_by())
        featureproducedbyvariants = list(FeatureProducedByVariant.objects.order_by())
        # Data
        self.id_to_card = {c.id: c for c in cards}
        self.id_to_template = {t.id: t for t in templates}
        self.id_to_feature_of_card = {f.id: f for f in featureofcards}
        self.id_to_combo = {c.id: c for c in combos}
        self.id_to_variant = {v.id: v for v in variants}
        self.id_to_feature = {f.id: f for f in features}
        self.generator_combos = [c for c in combos if c.status == Combo.Status.GENERATOR]
        self.combo_to_cards = {c.id: list[CardInCombo]() for c in combos}
        for cardincombo in cardincombos:
            x = self.combo_to_cards.get(cardincombo.combo_id)
            if x is not None:
                x.append(cardincombo)
        for i in self.combo_to_cards.values():
            i.sort(key=lambda cic: cic.order)
        self.combo_to_templates = {c.id: list[TemplateInCombo]() for c in combos}
        for i in templateincombos:
            x = self.combo_to_templates.get(i.combo_id)
            if x is not None:
                x.append(i)
        for i in self.combo_to_templates.values():
            i.sort(key=lambda tic: tic.order)
        self.combo_to_produced_features = {c.id: list[FeatureProducedInCombo]() for c in combos}
        for i in featureproducedincombos:
            x = self.combo_to_produced_features.get(i.combo_id)
            if x is not None:
                x.append(i)
        self.combo_to_needed_features = {c.id: list[FeatureNeededInCombo]() for c in combos}
        for i in featureneededincombos:
            x = self.combo_to_needed_features.get(i.combo_id)
            if x is not None:
                x.append(i)
        self.combo_to_removed_features = {c.id: list[FeatureRemovedInCombo]() for c in combos}
        for i in featureremovedincombos:
            x = self.combo_to_removed_features.get(i.combo_id)
            if x is not None:
                x.append(i)

        self.feature_needed_in_combo_to_attributes_matcher = dict[int, AttributesMatcher]()
        feature_needed_in_combo_to_any_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_anyofattributes:
            x = feature_needed_in_combo_to_any_of_attributes.get(i.featureneededincombo_id)
            if x is not None:
                x.add(i.featureattribute_id)
        feature_needed_in_combo_to_all_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_allofattributes:
            x = feature_needed_in_combo_to_all_of_attributes.get(i.featureneededincombo_id)
            if x is not None:
                x.add(i.featureattribute_id)
        feature_needed_in_combo_to_none_of_attributes = {f.id: set[int]() for f in featureneededincombos}
        for i in featureneededincombo_noneofattributes:
            x = feature_needed_in_combo_to_none_of_attributes.get(i.featureneededincombo_id)
            if x is not None:
                x.add(i.featureattribute_id)
        for i in featureneededincombos:
            self.feature_needed_in_combo_to_attributes_matcher[i.id] = AttributesMatcher(
                any_of=frozenset(feature_needed_in_combo_to_any_of_attributes[i.id]),
                all_of=frozenset(feature_needed_in_combo_to_all_of_attributes[i.id]),
                none_of=frozenset(feature_needed_in_combo_to_none_of_attributes[i.id]),
            )
        self.feature_produced_in_combo_to_attributes = {f.id: set[int]() for f in featureproducedincombos}
        for i in featureproducedincombo_attributes:
            x = self.feature_produced_in_combo_to_attributes.get(i.featureproducedincombo_id)
            if x is not None:
                x.add(i.featureattribute_id)
        self.card_to_features = {c.id: list[FeatureOfCard]() for c in cards}
        self.features_to_cards = {f.id: list[FeatureOfCard]() for f in features}
        for i in featureofcards:
            x = self.card_to_features.get(i.card_id)
            y = self.features_to_cards.get(i.feature_id)
            if x is not None and y is not None:
                x.append(i)
                y.append(i)
        self.feature_of_card_to_attributes = {f.id: set[int]() for f in featureofcards}
        for i in featureofcard_attributes:
            x = self.feature_of_card_to_attributes.get(i.featureofcard_id)
            if x is not None:
                x.add(i.featureattribute_id)

        self.variant_to_cards = {v.id: set[CardInVariant]() for v in variants}
        for i in cardinvariants:
            x = self.variant_to_cards.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_uses_card_dict = {(c.card_id, c.variant_id): c for c in cardinvariants if c.card_id in self.id_to_card and c.variant_id in self.id_to_variant}

        self.variant_to_templates = {v.id: set[TemplateInVariant]() for v in variants}
        for i in templateinvariants:
            x = self.variant_to_templates.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_requires_template_dict = {(t.template_id, t.variant_id): t for t in templateinvariants if t.template_id in self.id_to_template and t.variant_id in self.id_to_variant}

        self.variant_to_of_sets = {v.id: set[VariantOfCombo]() for v in variants}
        for i in variantofcombos:
            x = self.variant_to_of_sets.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_of_combo_dict = {(v.combo_id, v.variant_id): v for v in variantofcombos if v.combo_id in self.id_to_combo and v.variant_id in self.id_to_variant}

        self.variant_to_includes_sets = {v.id: set[VariantIncludesCombo]() for v in variants}
        for i in variantincludescombos:
            x = self.variant_to_includes_sets.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_includes_combo_dict = {(v.combo_id, v.variant_id): v for v in variantincludescombos if v.combo_id in self.id_to_combo and v.variant_id in self.id_to_variant}

        self.variant_to_produces = {v.id: set[FeatureProducedByVariant]() for v in variants}
        for i in featureproducedbyvariants:
            x = self.variant_to_produces.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_produces_feature_dict = {(f.feature_id, f.variant_id): f for f in featureproducedbyvariants if f.feature_id in self.id_to_feature and f.variant_id in self.id_to_variant}
        self.utility_features_ids = frozenset(f.id for f in self.id_to_feature.values() if f.is_utility)


count = 0


def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
    return count
