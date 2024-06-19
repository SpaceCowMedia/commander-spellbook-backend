from django.db import models
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH
from .utils import recipe


class Recipe(models.Model):
    name = models.CharField(max_length=MAX_CARD_NAME_LENGTH * 10 + MAX_FEATURE_NAME_LENGTH * 5 + 100, editable=False)

    def cards(self) -> dict[str, int]:
        return {}

    def templates(self) -> dict[str, int]:
        return {}

    def features_needed(self) -> dict[str, int]:
        return {}

    def features_produced(self) -> dict[str, int]:
        return {}

    def _str(self) -> str:
        if self.pk is None:
            base = f'New {self._meta.model_name}'
            if hasattr(self, 'id') and self.id is not None:  # type: ignore
                base += f' with unique id <{self.id}>'  # type: ignore
            return base
        return self.compute_name(self.cards(), self.templates(), self.features_needed(), self.features_produced())

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
    ) -> str:

        def element(name: str, quantity: int) -> str:
            return f'{quantity} {name}' if quantity > 1 else name
        return recipe(
            [element(card, q) for card, q in cards.items()] + [element(feature, q) for feature, q in features_needed.items()] + [element(template, q) for template, q in templates.items()],
            [element(feature, q) for feature, q in features_produced.items()][:4]
        )

    class Meta:
        abstract = True
