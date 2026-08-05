from functools import cache
from django.db import models
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH
from .utils import recipe, DEFAULT_BATCH_SIZE


class Recipe(models.Model):
    name = models.CharField(default='', max_length=MAX_CARD_NAME_LENGTH * 10 + MAX_FEATURE_NAME_LENGTH * 5 + 100, editable=False)
    ingredient_count = models.PositiveSmallIntegerField(default=0, editable=False)
    card_count = models.PositiveIntegerField(default=0, editable=False)
    template_count = models.PositiveIntegerField(default=0, editable=False)
    result_count = models.PositiveIntegerField(default=0, editable=False)

    def cards(self) -> dict[str, int]:
        return {}

    def templates(self) -> dict[str, int]:
        return {}

    def features_needed(self) -> dict[str, int]:
        return {}

    def features_produced(self) -> dict[str, int]:
        return {}

    def features_removed(self) -> dict[str, int]:
        return {}

    @classmethod
    @cache
    def recipe_fields(cls) -> list[str]:
        return [
            'name',
            'ingredient_count',
            'card_count',
            'template_count',
            'result_count',
        ]

    def _str(self) -> str:
        if self.pk is None:
            base = f'New {self._meta.model_name}'
            if hasattr(self, 'id') and self.id is not None:  # type: ignore
                base += f' with unique id <{self.id}>'  # type: ignore
            return base
        return self.compute_name(self.cards(), self.templates(), self.features_needed(), self.features_produced(), self.features_removed())

    def __str__(self) -> str:
        if self.name:
            return self.name
        return self._str()

    @classmethod
    def compute_name(
        cls,
        cards: dict[str, int],
        templates: dict[str, int],
        features_needed: dict[str, int],
        features_produced: dict[str, int],
        features_removed: dict[str, int],
    ) -> str:

        def element(name: str, quantity: int) -> str:
            return f'{quantity} {name}' if quantity > 1 else name
        return recipe(
            ingredients=[element(card, q) for card, q in cards.items()] + [element(feature, q) for feature, q in features_needed.items()] + [element(template, q) for template, q in templates.items()],
            results=[element(feature, q) for feature, q in features_produced.items()],
            negative_results=[element(feature, q) for feature, q in features_removed.items()],
        )

    @classmethod
    def compute_ingredient_count(cls, cards: dict[str, int], templates: dict[str, int], features_needed: dict[str, int]) -> int:
        return sum(cards.values()) + sum(templates.values()) + sum(features_needed.values())

    @classmethod
    def compute_card_count(cls, cards: dict[str, int], templates: dict[str, int], features_needed: dict[str, int]) -> int:
        return sum(cards.values()) + sum(templates.values())

    @classmethod
    def compute_result_count(cls, features_produced: dict[str, int]) -> int:
        return sum(features_produced.values())

    @classmethod
    def compute_template_count(cls, templates: dict[str, int]) -> int:
        return sum(templates.values())

    def update_recipe_from_memory(
            self,
            cards: dict[str, int],
            templates: dict[str, int],
            features_needed: dict[str, int],
            features_produced: dict[str, int],
            features_removed: dict[str, int],
    ) -> bool:
        previous_values = {field: getattr(self, field) for field in self.recipe_fields()}
        self.name = self.compute_name(cards, templates, features_needed, features_produced, features_removed)
        self.ingredient_count = self.compute_ingredient_count(cards, templates, features_needed)
        self.card_count = self.compute_card_count(cards, templates, features_needed)
        self.template_count = self.compute_template_count(templates)
        self.result_count = self.compute_result_count(features_produced)
        updated_values = {field: getattr(self, field) for field in self.recipe_fields()}
        return previous_values != updated_values

    def update_recipe_from_data(self) -> bool:
        return self.update_recipe_from_memory(
            self.cards(),
            self.templates(),
            self.features_needed(),
            self.features_produced(),
            self.features_removed(),
        )

    class Meta:
        abstract = True


def update_variants(**ingredient_filter) -> None:
    '''Recomputes every field a variant derives from the ingredient matched by the filter.'''
    from .variant import Variant
    # the ids are taken upfront, unordered, to load the recipes themselves in bounded batches
    variant_ids = list(Variant.objects.filter(**ingredient_filter).order_by().values_list('pk', flat=True))
    for i in range(0, len(variant_ids), DEFAULT_BATCH_SIZE):
        variants_to_save = []
        variants: models.QuerySet[Variant] = Variant.recipes_prefetched.filter(pk__in=variant_ids[i:i + DEFAULT_BATCH_SIZE]).order_by()
        for variant in variants:
            if variant.update_variant():
                variants_to_save.append(variant)
        Variant.objects.bulk_update(variants_to_save, fields=Variant.computed_fields(), batch_size=DEFAULT_BATCH_SIZE)


def update_combo_names(**ingredient_filter) -> None:
    '''Recomputes the names of the combos using the ingredient matched by the filter, the only thing they derive from it.'''
    from .combo import Combo
    combo_ids = list(Combo.objects.filter(**ingredient_filter).order_by().values_list('pk', flat=True))
    for i in range(0, len(combo_ids), DEFAULT_BATCH_SIZE):
        combos_to_save = []
        # only the name is read and written, the rest of the recipe comes from the prefetched rows
        combos: models.QuerySet[Combo] = Combo.recipes_prefetched.filter(pk__in=combo_ids[i:i + DEFAULT_BATCH_SIZE]).order_by().only('name')
        for combo in combos:
            new_combo_name = combo._str()
            if new_combo_name != combo.name:
                combo.name = new_combo_name
                combos_to_save.append(combo)
        Combo.objects.bulk_update(combos_to_save, fields=['name'], batch_size=DEFAULT_BATCH_SIZE)
