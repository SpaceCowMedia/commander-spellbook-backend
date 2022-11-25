from collections import defaultdict
from ..models import Card, Feature, Combo, Template, Variant
from django.db import connection
from django.db import reset_queries
import logging
from django.conf import settings

def fetch_not_working_variants(variants_base_query):
    res = variants_base_query.filter(status=Variant.Status.NOT_WORKING).values('id', 'uses__id')
    d = defaultdict(set)
    for r in res:
        d[r['id']].add(r['uses__id'])
    return [frozenset(s) for s in d.values()]

class Data:
    def __init__(self):
        self.combos = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces')
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.variants = Variant.objects.prefetch_related('uses', 'requires')
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.templates = Template.objects.prefetch_related('required_by_combos')
        self.not_working_variants = fetch_not_working_variants(self.variants)

count = 0
def debug_queries(output=False):
    global count
    if settings.DEBUG:
        count += len(connection.queries)
        reset_queries()
        if output:
            logging.info(f'Number of queries so far: {count}')
