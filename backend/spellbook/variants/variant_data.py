import logging
from django.conf import settings
from django.db import connection, reset_queries
from collections import defaultdict
from spellbook.models.card import Card, FeatureOfCard
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo, CardInCombo, TemplateInCombo
from spellbook.models.template import Template
from spellbook.models.variant import Variant, CardInVariant, TemplateInVariant


class Data:
    def __init__(self, single_combo: Combo | None = None):
        combos_query = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces').filter(status__in=(Combo.Status.GENERATOR, Combo.Status.GENERATOR_WITH_MANY_CARDS, Combo.Status.UTILITY))
        if single_combo is not None:
            combos_query = combos_query.filter(included_in_variants__includes=single_combo).distinct()
        self.combos = list(combos_query)
        self.combo_to_cards = defaultdict[int, list[CardInCombo]](list)
        self.combo_to_templates = defaultdict[int, list[TemplateInCombo]](list)
        self.card_to_features = defaultdict[int, list[FeatureOfCard]](list)
        self.generator_combos = [c for c in self.combos if c.status in (Combo.Status.GENERATOR, Combo.Status.GENERATOR_WITH_MANY_CARDS)]
        card_in_combos = CardInCombo.objects.select_related('card', 'combo').filter(combo__in=self.combos)
        template_in_combos = TemplateInCombo.objects.select_related('template', 'combo').filter(combo__in=self.combos)
        features_in_cards = FeatureOfCard.objects.select_related('feature', 'card')
        for cic in card_in_combos:
            self.combo_to_cards[cic.combo.id].append(cic)
        for tic in template_in_combos:
            self.combo_to_templates[tic.combo.id].append(tic)
        for fic in features_in_cards:
            self.card_to_features[fic.card.id].append(fic)
        for combo_to_cards in self.combo_to_cards.values():
            combo_to_cards.sort(key=lambda cic: cic.order)
        for combo_to_templates in self.combo_to_templates.values():
            combo_to_templates.sort(key=lambda tic: tic.order)
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.id_to_card: dict[int, Card] = {c.id: c for c in self.cards}
        self.templates = Template.objects.prefetch_related('required_by_combos')
        self.id_to_template: dict[int, Template] = {t.id: t for t in self.templates}

        def fetch_not_working_variants(variants_base_query):
            res = variants_base_query.filter(status=Variant.Status.NOT_WORKING).values('id', 'uses__id')
            d = defaultdict[str, set[int]](set)
            for r in res:
                d[r['id']].add(r['uses__id'])
            return [frozenset(s) for s in d.values()]

        def fetch_removed_features(combos: list[Combo]):
            d = defaultdict[int, set[int]](set)
            for c in combos:
                for r in c.removes.all():
                    d[c.id].add(r.id)
            return d

        self.variants = Variant.objects.all()
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.not_working_variants = fetch_not_working_variants(self.variants)
        self.id_to_variant = {v.id: v for v in self.variants}
        self.id_to_combo: dict[int, Combo] = {c.id: c for c in self.combos}
        self.card_in_variant = {(civ.card.id, civ.variant.id): civ for civ in CardInVariant.objects.select_related('card', 'variant')}
        self.template_in_variant = {(tiv.template.id, tiv.variant.id): tiv for tiv in TemplateInVariant.objects.select_related('template', 'variant')}
        self.combo_to_removed_features = fetch_removed_features(self.combos)
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.id_to_feature: dict[int, Feature] = {f.id: f for f in self.features}


count = 0


def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
    return count
