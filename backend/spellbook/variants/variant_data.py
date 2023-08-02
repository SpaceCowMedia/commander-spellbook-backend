import logging
from django.conf import settings
from django.db import connection, reset_queries
from collections import defaultdict
from spellbook.models.card import Card
from spellbook.models.feature import Feature
from spellbook.models.combo import Combo, CardInCombo, TemplateInCombo
from spellbook.models.template import Template
from spellbook.models.variant import Variant, CardInVariant, TemplateInVariant


class RestoreData:
    def __init__(self):
        self.combos = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces').filter(kind__in=(Combo.Kind.GENERATOR, Combo.Kind.GENERATOR_WITH_MANY_CARDS, Combo.Kind.UTILITY))
        self.combo_to_cards = defaultdict[int, list[CardInCombo]](list)
        self.combo_to_templates = defaultdict[int, list[TemplateInCombo]](list)
        self.generator_combos = list(self.combos.filter(kind__in=(Combo.Kind.GENERATOR, Combo.Kind.GENERATOR_WITH_MANY_CARDS)))
        for cic in CardInCombo.objects.select_related('card', 'combo').distinct():
            self.combo_to_cards[cic.combo.id].append(cic)
        for tic in TemplateInCombo.objects.select_related('template', 'combo').distinct():
            self.combo_to_templates[tic.combo.id].append(tic)
        for combo_to_cards in self.combo_to_cards.values():
            combo_to_cards.sort(key=lambda cic: cic.order)
        for combo_to_templates in self.combo_to_templates.values():
            combo_to_templates.sort(key=lambda tic: tic.order)


class Data(RestoreData):
    def __init__(self):
        def fetch_not_working_variants(variants_base_query):
            res = variants_base_query.filter(status=Variant.Status.NOT_WORKING).values('id', 'uses__id')
            d = defaultdict[str, set[int]](set)
            for r in res:
                d[r['id']].add(r['uses__id'])
            return [frozenset(s) for s in d.values()]

        def fetch_removed_features(combos_base_query):
            res = combos_base_query.values('id', 'removes__id')
            d = defaultdict[int, set[int]](set)
            for r in res:
                if r['removes__id'] is not None:
                    d[r['id']].add(r['removes__id'])
            return d

        super().__init__()
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.variants = Variant.objects.all()
        self.templates = Template.objects.prefetch_related('required_by_combos')
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.not_working_variants = fetch_not_working_variants(self.variants)
        self.id_to_variant = {v.id: v for v in self.variants}
        self.id_to_combo: dict[int, Combo] = {c.id: c for c in self.combos}
        self.id_to_card: dict[int, Card] = {c.id: c for c in self.cards}
        self.id_to_template: dict[int, Template] = {t.id: t for t in self.templates}
        self.card_in_variant = {(civ.card.id, civ.variant.id): civ for civ in CardInVariant.objects.select_related('card', 'variant')}
        self.template_in_variant = {(tiv.template.id, tiv.variant.id): tiv for tiv in TemplateInVariant.objects.select_related('template', 'variant')}
        self.combo_to_removed_features = fetch_removed_features(self.combos)


count = 0


def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
    return count
