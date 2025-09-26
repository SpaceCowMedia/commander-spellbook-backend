from django.db import models
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH
from .utils import recipe


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

    def update_recipe_from_memory(self, cards: dict[str, int], templates: dict[str, int], features_needed: dict[str, int], features_produced: dict[str, int], features_removed: dict[str, int]):
        self.name = self.compute_name(cards, templates, features_needed, features_produced, features_removed)
        self.ingredient_count = self.compute_ingredient_count(cards, templates, features_needed)
        self.card_count = self.compute_card_count(cards, templates, features_needed)
        self.template_count = self.compute_template_count(templates)
        self.result_count = self.compute_result_count(features_produced)

    def update_recipe_from_data(self):
        self.update_recipe_from_memory(self.cards(), self.templates(), self.features_needed(), self.features_produced(), self.features_removed())

    class Meta:
        abstract = True
