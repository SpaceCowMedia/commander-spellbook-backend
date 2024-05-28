import logging
from multiset import FrozenMultiset
from django.conf import settings
from django.db import connection, reset_queries
from spellbook.models.card import Card, FeatureOfCard
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo, CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo
from spellbook.models.template import Template
from spellbook.models.variant import Variant, CardInVariant, TemplateInVariant, FeatureProducedByVariant, VariantOfCombo, VariantIncludesCombo
from .variant_set import VariantSet


class Data:
    def __init__(
            self,
            cards: list[Card] | None = None,
            features: list[Feature] | None = None,
            combos: list[Combo] | None = None,
            templates: list[Template] | None = None,
            variants: list[Variant] | None = None,
    ):
        if combos is None:
            self.combos = list(Combo.objects.filter(status__in=(Combo.Status.GENERATOR, Combo.Status.UTILITY)).prefetch_related(
                'cardincombo_set',
                'templateincombo_set',
                'featureproducedincombo_set',
                'featureneededincombo_set',
                'featureremovedincombo_set',
            ))
        else:
            self.combos = combos
        self.id_to_combo: dict[int, Combo] = {c.id: c for c in self.combos}
        self.combo_to_cards = dict[int, list[CardInCombo]]()
        self.combo_to_templates = dict[int, list[TemplateInCombo]]()
        self.combo_to_produced_features = dict[int, list[FeatureProducedInCombo]]()
        self.combo_to_needed_features = dict[int, list[FeatureNeededInCombo]]()
        self.combo_to_removed_features = dict[int, list[FeatureRemovedInCombo]]()
        self.generator_combos = [c for c in self.combos if c.status == Combo.Status.GENERATOR]
        for combo in self.combos:
            self.combo_to_cards[combo.id] = list(combo.cardincombo_set.all())
            self.combo_to_templates[combo.id] = list(combo.templateincombo_set.all())
            self.combo_to_produced_features[combo.id] = list(combo.featureproducedincombo_set.all())
            self.combo_to_needed_features[combo.id] = list(combo.featureneededincombo_set.all())
            self.combo_to_removed_features[combo.id] = list(combo.featureremovedincombo_set.all())
        for combo_to_cards in self.combo_to_cards.values():
            combo_to_cards.sort(key=lambda cic: cic.order)
        for combo_to_templates in self.combo_to_templates.values():
            combo_to_templates.sort(key=lambda tic: tic.order)
        self.card_to_features = dict[int, list[FeatureOfCard]]()
        if cards is None:
            self.cards = list(Card.objects.prefetch_related(
                'featureofcard_set',
            ))
        else:
            self.cards = cards
        for card in self.cards:
            self.card_to_features[card.id] = list(card.featureofcard_set.all())
        self.id_to_card = {c.id: c for c in self.cards}
        if templates is None:
            self.templates = list(Template.objects.all())
        else:
            self.templates = templates
        self.id_to_template = {t.id: t for t in self.templates}

        def fetch_not_working_variants(variants: list[Variant]) -> VariantSet:
            variants = [v for v in variants if v.status == Variant.Status.NOT_WORKING]
            variant_set = VariantSet()
            for v in variants:
                variant_set.add(
                    FrozenMultiset({c.card_id: c.quantity for c in v.cardinvariant_set.all()}),  # type: ignore
                    FrozenMultiset({t.template_id: t.quantity for t in v.templateinvariant_set.all()}),  # type: ignore
                )
            return variant_set

        if features is None:
            self.features = list(Feature.objects.prefetch_related(
                'featureofcard_set',
                'featureneededincombo_set',
                'featureproducedincombo_set',
                'featureremovedincombo_set',
            ))
        else:
            self.features = features
        self.utility_features_ids = frozenset(f.id for f in self.features if f.utility)
        self.id_to_feature: dict[int, Feature] = {f.id: f for f in self.features}
        if variants is None:
            self.variants: list[Variant] = list(Variant.objects.prefetch_related(
                'cardinvariant_set',
                'templateinvariant_set',
                'variantofcombo_set',
                'variantincludescombo_set',
                'featureproducedbyvariant_set',
            ))
        else:
            self.variants = variants
        self.not_working_variants = fetch_not_working_variants(self.variants).variants()
        self.id_to_variant = {v.id: v for v in self.variants}
        self.card_in_variant = dict[str, list[CardInVariant]]()
        self.template_in_variant = dict[str, list[TemplateInVariant]]()
        self.card_variant_dict = dict[tuple[int, str], CardInVariant]()
        self.template_variant_dict = dict[tuple[int, str], TemplateInVariant]()
        self.variant_to_of = dict[str, dict[int, VariantOfCombo]]()
        self.variant_to_includes = dict[str, dict[int, VariantIncludesCombo]]()
        self.variant_to_produces = dict[str, dict[int, FeatureProducedByVariant]]()
        for variant in self.variants:
            cards_in_variant = list(variant.cardinvariant_set.all())
            templates_in_variant = list(variant.templateinvariant_set.all())
            self.card_in_variant[variant.id] = cards_in_variant
            self.template_in_variant[variant.id] = templates_in_variant
            self.variant_to_of[variant.id] = {o.combo_id: o for o in variant.variantofcombo_set.all()}  # type: ignore
            self.variant_to_includes[variant.id] = {i.combo_id: i for i in variant.variantincludescombo_set.all()}  # type: ignore
            self.variant_to_produces[variant.id] = {f.feature_id: f for f in variant.featureproducedbyvariant_set.all()}  # type: ignore
            for card_in_variant in cards_in_variant:
                self.card_variant_dict[(card_in_variant.card_id, variant.id)] = card_in_variant
            for template_in_variant in templates_in_variant:
                self.template_variant_dict[(template_in_variant.template_id, variant.id)] = template_in_variant


count = 0


def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
    return count
