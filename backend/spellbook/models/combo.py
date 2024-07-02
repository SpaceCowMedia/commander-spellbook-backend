from django.db import models
from django.db.models.signals import m2m_changed, post_save, post_delete
from django.dispatch import receiver
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from .mixins import ScryfallLinkMixin
from .recipe import Recipe
from .card import Card
from .feature import Feature
from .template import Template
from .ingredient import IngredientInCombination, ZoneLocationsField
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS
from .constants import HIGHER_CARD_LIMIT, DEFAULT_CARD_LIMIT, LOWER_VARIANT_LIMIT, DEFAULT_VARIANT_LIMIT
from .feature_attribute import WithFeatureAttributes, WithFeatureAttributesMatcher


class RecipePrefetchedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            models.Prefetch('uses', queryset=Card.objects.order_by('cardincombo')),
            models.Prefetch('requires', queryset=Template.objects.order_by('templateincombo')),
            'needs',
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
    notes = models.TextField(blank=True, help_text='Notes about the combo', validators=TEXT_VALIDATORS)
    status = models.CharField(choices=Status.choices, default=Status.GENERATOR, help_text='Is this combo a generator for variants?', verbose_name='status', max_length=2)
    allow_many_cards = models.BooleanField(default=False, help_text=f'Allow variants to have more cards ({HIGHER_CARD_LIMIT}) than the default limit ({DEFAULT_CARD_LIMIT}). On the other hand, with this option enabled, the limit on the number of allowed variants is lowered to {LOWER_VARIANT_LIMIT}, instead of the default {DEFAULT_VARIANT_LIMIT}.')
    allow_multiple_copies = models.BooleanField(default=False, help_text='Allow variants to have more copies of the same card or template')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def cards(self) -> dict[str, int]:
        return {c.card.name: c.quantity for c in self.cardincombo_set.all()}

    def templates(self) -> dict[str, int]:
        return {t.template.name: t.quantity for t in self.templateincombo_set.all()}

    def features_produced(self) -> dict[str, int]:
        return {f.feature.name: 1 for f in self.featureproducedincombo_set.all()}

    def features_needed(self) -> dict[str, int]:
        return {f.feature.name: f.quantity for f in self.featureneededincombo_set.all()}

    class Meta:
        verbose_name = 'combo'
        verbose_name_plural = 'combos'
        default_manager_name = 'objects'
        ordering = ['created']


class CardInCombo(IngredientInCombination):
    id: int
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.card} in combo {self.combo.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'combo')]


class TemplateInCombo(IngredientInCombination):
    id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.template} in combo {self.combo.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'combo')]


class FeatureNeededInCombo(WithFeatureAttributesMatcher):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int
    quantity = models.PositiveSmallIntegerField(default=1, blank=False, help_text='Quantity of the feature needed in the combo.', verbose_name='quantity', validators=[MinValueValidator(1)])
    zone_locations_override = ZoneLocationsField(blank=True, default='', verbose_name='zone locations override', help_text='Option to override the zone locations for the card(s) this feature replaces.')

    def __str__(self):
        return f'{self.feature} needed in combo {self.combo.pk}'

    class Meta:
        unique_together = [('feature', 'combo')]

    def clean(self):
        super().clean()
        if self.quantity > 1 and self.feature.uncountable:
            raise ValidationError('Uncountable features can only appear in one copy.')


class FeatureProducedInCombo(WithFeatureAttributes):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.feature} produced in combo {self.combo.pk}'

    class Meta:
        unique_together = [('feature', 'combo')]


class FeatureRemovedInCombo(models.Model):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

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
def recipe_changed_2(sender, instance: CardInCombo | TemplateInCombo | FeatureNeededInCombo | FeatureProducedInCombo | FeatureRemovedInCombo, **kwargs) -> None:
    instance.combo.name = instance.combo._str()
    instance.combo.save()
