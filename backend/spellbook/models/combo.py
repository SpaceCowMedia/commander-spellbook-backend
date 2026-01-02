from django.db import models
from django.db.models.signals import m2m_changed, post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .mixins import ScryfallLinkMixin
from .recipe import Recipe
from .card import Card
from .feature import Feature
from .template import Template
from .ingredient import Ingredient, IngredientInCombination, ZoneLocationsField
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS
from .constants import HIGHER_CARD_LIMIT, DEFAULT_CARD_LIMIT, LOWER_VARIANT_LIMIT, DEFAULT_VARIANT_LIMIT, MAX_MANA_NEEDED_LENGTH
from .feature_attribute import WithFeatureAttributes, WithFeatureAttributesMatcher


class RecipePrefetchedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'cardincombo_set',
            'cardincombo_set__card',
            'templateincombo_set',
            'templateincombo_set__template',
            'featureneededincombo_set',
            'featureneededincombo_set__feature',
            'featureproducedincombo_set',
            'featureproducedincombo_set__feature',
            'featureremovedincombo_set',
            'featureremovedincombo_set__feature',
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
        through='CardInCombo',
        related_name='used_in_combos',
        help_text='Cards that this combo uses',
        blank=True,
        verbose_name='used cards',
    )
    cardincombo_set: models.Manager['CardInCombo']
    needs = models.ManyToManyField(
        to=Feature,
        through='FeatureNeededInCombo',
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features',
    )
    featureneededincombo_set: models.Manager['FeatureNeededInCombo']
    requires = models.ManyToManyField(
        to=Template,
        through='TemplateInCombo',
        related_name='required_by_combos',
        help_text='Templates that this combo requires',
        blank=True,
        verbose_name='required templates',
    )
    templateincombo_set: models.Manager['TemplateInCombo']
    produces = models.ManyToManyField(
        to=Feature,
        through='FeatureProducedInCombo',
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features',
    )
    featureproducedincombo_set: models.Manager['FeatureProducedInCombo']
    removes = models.ManyToManyField(
        to=Feature,
        through='FeatureRemovedInCombo',
        related_name='removed_by_combos',
        help_text='Features that this combo removes',
        blank=True,
        verbose_name='removed features',
    )
    featureremovedincombo_set: models.Manager['FeatureRemovedInCombo']
    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR, *TEXT_VALIDATORS])
    easy_prerequisites = models.TextField(blank=True, help_text='Easily achievable prerequisites for this combo.', validators=TEXT_VALIDATORS)
    notable_prerequisites = models.TextField(blank=True, help_text='Notable prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description of the combo, in steps. Here and in every other text field you can reference feature replacements with the [[name]] syntax. Optionally, you can also give it an alias to use later with [[name|alias]] and/or select one of the multiple copies with [[name$number]].', validators=TEXT_VALIDATORS)
    notes = models.TextField(blank=True, help_text='Notes about the combo that will be displayed on the site', validators=TEXT_VALIDATORS)
    status = models.CharField(choices=Status.choices, default=Status.DRAFT, help_text='Is this combo a generator for variants?', verbose_name='status', max_length=2)
    allow_many_cards = models.BooleanField(default=False, help_text=f'Allow variants to have more cards ({HIGHER_CARD_LIMIT}) than the default limit ({DEFAULT_CARD_LIMIT}). On the other hand, with this option enabled, the limit on the number of allowed variants is lowered to {LOWER_VARIANT_LIMIT}, instead of the default {DEFAULT_VARIANT_LIMIT}.')
    allow_multiple_copies = models.BooleanField(default=False, help_text='Allow variants to have more copies of the same card or template')
    comment = models.TextField(blank=True, help_text='Notes about the combo', validators=TEXT_VALIDATORS)
    variant_count = models.PositiveIntegerField(default=0, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    def cards(self) -> dict[str, int]:
        return {c.card.name: c.quantity for c in self.cardincombo_set.all()}

    def templates(self) -> dict[str, int]:
        return {t.template.name: t.quantity for t in self.templateincombo_set.all()}

    def features_produced(self) -> dict[str, int]:
        return {f.feature.name: 1 for f in self.featureproducedincombo_set.all()}

    def features_removed(self) -> dict[str, int]:
        return {f.feature.name: 1 for f in self.featureremovedincombo_set.all()}

    def features_needed(self) -> dict[str, int]:
        result = dict[str, int]()
        for f in self.featureneededincombo_set.all():
            result[f.feature.name] = result.get(f.feature.name, 0) + f.quantity
        return result

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
        return f'{self.card} in combo {self.combo_id}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'combo')]


class TemplateInCombo(IngredientInCombination):
    id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.template} in combo {self.combo_id}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'combo')]


class FeatureNeededInCombo(Ingredient, WithFeatureAttributesMatcher):
    id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int
    zone_locations = ZoneLocationsField(blank=True, verbose_name='starting locations override', help_text='Override the starting locations for this feature replacements in this combo.')

    def __str__(self):
        return f'{self.feature} needed in combo {self.combo_id}'

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
        return f'{self.feature} produced in combo {self.combo_id}'


class FeatureRemovedInCombo(models.Model):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.feature} removed in combo {self.combo_id}'

    class Meta:
        unique_together = [('feature', 'combo')]


@receiver(m2m_changed, sender=Combo.needs.through, dispatch_uid='combo_needs_changed2')
@receiver(m2m_changed, sender=Combo.produces.through, dispatch_uid='combo_produces_changed2')
@receiver(m2m_changed, sender=Combo.removes.through, dispatch_uid='combo_removes_changed2')
def recipe_changed(sender, instance: Recipe, action: str, reverse: bool, model: models.Model, pk_set: set[int], **kwargs):
    if action.startswith('post_'):
        if instance.update_recipe_from_data():
            instance.save(update_fields=Recipe.recipe_fields())


@receiver([post_save, post_delete], sender=Combo.uses.through, dispatch_uid='combo_uses_changed')
@receiver([post_save, post_delete], sender=Combo.requires.through, dispatch_uid='combo_templates_changed')
@receiver([post_save, post_delete], sender=Combo.needs.through, dispatch_uid='combo_needs_changed')
@receiver([post_save, post_delete], sender=Combo.produces.through, dispatch_uid='combo_produces_changed')
@receiver([post_save, post_delete], sender=Combo.removes.through, dispatch_uid='combo_removes_changed')
def recipe_changed_2(sender, instance: CardInCombo | TemplateInCombo | FeatureNeededInCombo | FeatureProducedInCombo | FeatureRemovedInCombo, raw=False, **kwargs):
    if raw:
        return
    if instance.combo.update_recipe_from_data():
        instance.combo.save(update_fields=Recipe.recipe_fields())
