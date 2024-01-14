from django.db import models
from django.db.models.signals import m2m_changed, post_save, post_delete
from django.dispatch import receiver
from .mixins import ScryfallLinkMixin
from .card import Card
from .feature import Feature
from .template import Template
from .ingredient import IngredientInCombination, Recipe
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS


class Combo(Recipe, ScryfallLinkMixin):
    class Kind(models.TextChoices):
        GENERATOR = 'G'
        UTILITY = 'U'
        GENERATOR_WITH_MANY_CARDS = 'M'
        DRAFT = 'D'

    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_combos',
        help_text='Cards that this combo uses',
        blank=True,
        verbose_name='used cards',
        through='CardInCombo')
    needs = models.ManyToManyField(
        to=Feature,
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features')
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_combos',
        help_text='Templates that this combo requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInCombo')
    produces = models.ManyToManyField(
        to=Feature,
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features')
    removes = models.ManyToManyField(
        to=Feature,
        related_name='removed_by_combos',
        help_text='Features that this combo removes',
        blank=True,
        verbose_name='removed features')
    mana_needed = models.CharField(blank=True, max_length=200, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of the combo, in steps', validators=TEXT_VALIDATORS)
    kind = models.CharField(choices=Kind.choices, default=Kind.GENERATOR, help_text='Is this combo a generator for variants?', verbose_name='kind', max_length=2)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def cards(self) -> list[Card]:
        return list(self.uses.order_by('cardincombo'))

    def templates(self) -> list[Template]:
        return list(self.requires.order_by('templateincombo'))

    def features_produced(self) -> list[Feature]:
        return list(self.produces.all())

    def features_needed(self) -> list[Feature]:
        return list(self.needs.all())

    class Meta:
        ordering = ['created']
        verbose_name = 'combo'
        verbose_name_plural = 'combos'


class CardInCombo(IngredientInCombination):
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.card} in combo {self.combo.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'combo')]


class TemplateInCombo(IngredientInCombination):
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.template} in combo {self.combo.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'combo')]


@receiver(m2m_changed, sender=Combo.needs.through, dispatch_uid='combo_needs_changed')
@receiver(m2m_changed, sender=Combo.produces.through, dispatch_uid='combo_produces_changed')
@receiver(m2m_changed, sender=Combo.removes.through, dispatch_uid='combo_removes_changed')
def recipe_changed(sender, instance: Recipe, action: str, reverse: bool, model: models.Model, pk_set: set[int], **kwargs) -> None:
    if action.startswith('post_'):
        instance.name = instance._str()
        instance.save()


@receiver(post_save, sender=CardInCombo, dispatch_uid='combo_uses_changed')
@receiver(post_delete, sender=CardInCombo, dispatch_uid='combo_uses_changed')
@receiver(post_save, sender=TemplateInCombo, dispatch_uid='combo_templates_changed')
@receiver(post_delete, sender=TemplateInCombo, dispatch_uid='combo_templates_changed')
def recipe_changed_2(sender, instance: CardInCombo, **kwargs) -> None:
    instance.combo.name = instance.combo._str()
    instance.combo.save()
