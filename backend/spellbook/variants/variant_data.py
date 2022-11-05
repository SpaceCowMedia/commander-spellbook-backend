from ..models import Card, Feature, Combo, Template, Variant


class Data:
    def __init__(self):
        self.combos = Combo.objects.prefetch_related('uses', 'requires', 'needs', 'removes', 'produces')
        self.features = Feature.objects.prefetch_related('cards', 'produced_by_combos', 'needed_by_combos', 'removed_by_combos')
        self.cards = Card.objects.prefetch_related('features', 'used_in_combos')
        self.variants = Variant.objects.prefetch_related('uses', 'requires')
        self.utility_features_ids = frozenset[int](Feature.objects.filter(utility=True).values_list('id', flat=True))
        self.templates = Template.objects.prefetch_related('required_by_combos')
        self.not_working_variants = [frozenset[int](v.uses.values_list('id', flat=True)) for v in self.variants.filter(status=Variant.Status.NOT_WORKING)]
