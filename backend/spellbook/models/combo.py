from django.db import models
from django.db.models.signals import m2m_changed, post_save, post_delete
from django.dispatch import receiver
from django.core.validators import MinValueValidator
from .mixins import ScryfallLinkMixin
from .card import Card
from .feature import Feature
from .template import Template
from .ingredient import IngredientInCombination, Recipe
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS


class RecipePrefetchedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            models.Prefetch('uses', queryset=Card.objects.order_by('cardincombo')),
            'needs',
            models.Prefetch('requires', queryset=Template.objects.order_by('templateincombo')),
            'produces',
            'cardincombo_set',
            'templateincombo_set',
        )


class Combo(Recipe, ScryfallLinkMixin):
    objects = models.Manager()
    recipes_prefetched = RecipePrefetchedManager()

    class Status(models.TextChoices):
        GENERATOR = 'G'
        UTILITY = 'U'
        GENERATOR_WITH_MANY_CARDS = 'M'
        DRAFT = 'D'
        NEEDS_REVIEW = 'NR'

    id: int
    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_combos',
        help_text='Cards that this combo uses',
        blank=True,
        verbose_name='used cards',
        through='CardInCombo')
    cardincombo_set: models.Manager['CardInCombo']
    needs = models.ManyToManyField(
        to=Feature,
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features',
        through='FeatureNeededInCombo')
    featureneededincombo_set: models.Manager['FeatureNeededInCombo']
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_combos',
        help_text='Templates that this combo requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInCombo')
    templateincombo_set: models.Manager['TemplateInCombo']
    produces = models.ManyToManyField(
        to=Feature,
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features',
        through='FeatureProducedInCombo')
    featureproducedincombo_set: models.Manager['FeatureProducedInCombo']
    removes = models.ManyToManyField(
        to=Feature,
        related_name='removed_by_combos',
        help_text='Features that this combo removes',
        blank=True,
        verbose_name='removed features',
        through='FeatureRemovedInCombo')
    featureremovedincombo_set: models.Manager['FeatureRemovedInCombo']
    mana_needed = models.CharField(blank=True, max_length=200, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of the combo, in steps', validators=TEXT_VALIDATORS)
    status = models.CharField(choices=Status.choices, default=Status.GENERATOR, help_text='Is this combo a generator for variants?', verbose_name='status', max_length=2)
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
        verbose_name = 'combo'
        verbose_name_plural = 'combos'
        default_manager_name = 'objects'
        ordering = ['created']


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


class FeatureNeededInCombo(models.Model):
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    quantity = models.PositiveSmallIntegerField(default=1, blank=False, help_text='Quantity of the feature needed in the combo.', verbose_name='quantity', validators=[MinValueValidator(1)])

    def __str__(self):
        return f'{self.feature} needed in combo {self.combo.pk}'

    class Meta:
        unique_together = [('feature', 'combo')]


class FeatureProducedInCombo(models.Model):
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.feature} produced in combo {self.combo.pk}'

    class Meta:
        unique_together = [('feature', 'combo')]


class FeatureRemovedInCombo(models.Model):
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.feature} removed in combo {self.combo.pk}'

    class Meta:
        unique_together = [('feature', 'combo')]


@receiver(m2m_changed, sender=Combo.needs.through, dispatch_uid='combo_needs_changed2')
@receiver(m2m_changed, sender=Combo.produces.through, dispatch_uid='combo_produces_changed2')
@receiver(m2m_changed, sender=Combo.removes.through, dispatch_uid='combo_removes_changed2')
def recipe_changed(sender, instance: Recipe, action: str, reverse: bool, model: models.Model, pk_set: set[int], **kwargs) -> None:
    if action.startswith('post_'):
        instance.name = instance._str()
        instance.save()


@receiver([post_save, post_delete], sender=Combo.uses.through, dispatch_uid='combo_uses_changed')
@receiver([post_save, post_delete], sender=Combo.requires.through, dispatch_uid='combo_templates_changed')
@receiver([post_save, post_delete], sender=Combo.needs.through, dispatch_uid='combo_needs_changed')
@receiver([post_save, post_delete], sender=Combo.produces.through, dispatch_uid='combo_produces_changed')
@receiver([post_save, post_delete], sender=Combo.removes.through, dispatch_uid='combo_removes_changed')
def recipe_changed_2(sender, instance: CardInCombo, **kwargs) -> None:
    instance.combo.name = instance.combo._str()
    instance.combo.save()
