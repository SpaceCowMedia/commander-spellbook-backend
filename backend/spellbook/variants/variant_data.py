from dataclasses import dataclass, fields
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
        # Check any_of condition (isdisjoint runs at C level and exits early)
        if self.any_of and self.any_of.isdisjoint(attributes):
            return False
        # Check all_of condition
        if not (self.all_of <= attributes):
            return False
        # Check none_of condition (isdisjoint avoids allocating an intersection set)
        if self.none_of and not self.none_of.isdisjoint(attributes):
            return False
        return True


# Lightweight read-only rows for the variant relation tables.
# These tables dominate memory usage during generation, so they are loaded
# with values_list() instead of being materialized as Django model instances.

@dataclass(frozen=True, slots=True)
class VariantRow:
    id: str
    status: str
    name: str


@dataclass(frozen=True, slots=True)
class CardInVariantRow:
    id: int
    card_id: int
    variant_id: str
    zone_locations: str
    battlefield_card_state: str
    exile_card_state: str
    graveyard_card_state: str
    library_card_state: str
    must_be_commander: bool
    order: int
    quantity: int
    used_face: int | None


@dataclass(frozen=True, slots=True)
class TemplateInVariantRow:
    id: int
    template_id: int
    variant_id: str
    zone_locations: str
    battlefield_card_state: str
    exile_card_state: str
    graveyard_card_state: str
    library_card_state: str
    must_be_commander: bool
    order: int
    quantity: int


@dataclass(frozen=True, slots=True)
class FeatureProducedByVariantRow:
    id: int
    feature_id: int
    variant_id: str
    quantity: int


@dataclass(frozen=True, slots=True)
class VariantOfComboRow:
    id: int
    combo_id: int
    variant_id: str


@dataclass(frozen=True, slots=True)
class VariantIncludesComboRow:
    id: int
    combo_id: int
    variant_id: str


def _load_rows(row_class, queryset):
    '''Loads lightweight rows via values_list, using the row dataclass field names as the model field names.'''
    field_names = [field.name for field in fields(row_class)]
    return [row_class(*row) for row in queryset.order_by().values_list(*field_names)]


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
        # Variants, loaded as lightweight rows instead of model instances
        variants = _load_rows(VariantRow, Variant.objects)
        cardinvariants = _load_rows(CardInVariantRow, CardInVariant.objects)
        templateinvariants = _load_rows(TemplateInVariantRow, TemplateInVariant.objects)
        variantofcombos = _load_rows(VariantOfComboRow, VariantOfCombo.objects)
        variantincludescombos = _load_rows(VariantIncludesComboRow, VariantIncludesCombo.objects)
        featureproducedbyvariants = _load_rows(FeatureProducedByVariantRow, FeatureProducedByVariant.objects)
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

        self.variant_to_cards = {v.id: set[CardInVariantRow]() for v in variants}
        for i in cardinvariants:
            x = self.variant_to_cards.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_uses_card_dict = {(c.card_id, c.variant_id): c for c in cardinvariants if c.card_id in self.id_to_card and c.variant_id in self.id_to_variant}

        self.variant_to_templates = {v.id: set[TemplateInVariantRow]() for v in variants}
        for i in templateinvariants:
            x = self.variant_to_templates.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_requires_template_dict = {(t.template_id, t.variant_id): t for t in templateinvariants if t.template_id in self.id_to_template and t.variant_id in self.id_to_variant}

        self.variant_to_of_sets = {v.id: set[VariantOfComboRow]() for v in variants}
        for i in variantofcombos:
            x = self.variant_to_of_sets.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_of_combo_dict = {(v.combo_id, v.variant_id): v for v in variantofcombos if v.combo_id in self.id_to_combo and v.variant_id in self.id_to_variant}

        self.variant_to_includes_sets = {v.id: set[VariantIncludesComboRow]() for v in variants}
        for i in variantincludescombos:
            x = self.variant_to_includes_sets.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_includes_combo_dict = {(v.combo_id, v.variant_id): v for v in variantincludescombos if v.combo_id in self.id_to_combo and v.variant_id in self.id_to_variant}

        self.variant_to_produces = {v.id: set[FeatureProducedByVariantRow]() for v in variants}
        for i in featureproducedbyvariants:
            x = self.variant_to_produces.get(i.variant_id)
            if x is not None:
                x.add(i)
        self.variant_produces_feature_dict = {(f.feature_id, f.variant_id): f for f in featureproducedbyvariants if f.feature_id in self.id_to_feature and f.variant_id in self.id_to_variant}
        self.utility_features_ids = frozenset(f.id for f in self.id_to_feature.values() if f.is_utility)

    def fetch_variants(self, ids) -> dict[str, Variant]:
        '''Hydrates full Variant model instances for the given ids, in chunks.'''
        result = dict[str, Variant]()
        ids = list(ids)
        chunk_size = 900  # keeps the number of query parameters below common database limits
        for i in range(0, len(ids), chunk_size):
            for v in Variant.objects.order_by().filter(pk__in=ids[i:i + chunk_size]):
                result[v.id] = v
        return result
