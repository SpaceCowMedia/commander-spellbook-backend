from django.db import models
from django.db.models.signals import m2m_changed, post_save, post_delete
from django.dispatch import receiver
from django.core.exceptions import ValidationError
from .mixins import ScryfallLinkMixin
from .recipe import Recipe
from .explanation import Explanation
from .card import Card, WithUsedFace
from .feature import Feature
from .template import Template
from .ingredient import ComboIngredient, ZoneLocationsField
from .constants import HIGHER_CARD_LIMIT, DEFAULT_CARD_LIMIT, LOWER_VARIANT_LIMIT, DEFAULT_VARIANT_LIMIT
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


class RenamePrefetchedManager(models.Manager):
    '''Prefetches only what recomputing the name of a combo reads, with the ingredients joined to the
    names they display, so that a rename does not build the rest of the recipe.'''
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            models.Prefetch('cardincombo_set', queryset=CardInCombo.objects.select_related('card').only('combo_id', 'quantity', 'card__name')),
            models.Prefetch('templateincombo_set', queryset=TemplateInCombo.objects.select_related('template').only('combo_id', 'quantity', 'template__name')),
            models.Prefetch('featureneededincombo_set', queryset=FeatureNeededInCombo.objects.select_related('feature').only('combo_id', 'quantity', 'feature__name')),
            models.Prefetch('featureproducedincombo_set', queryset=FeatureProducedInCombo.objects.select_related('feature').only('combo_id', 'feature__name')),
            models.Prefetch('featureremovedincombo_set', queryset=FeatureRemovedInCombo.objects.select_related('feature').only('combo_id', 'feature__name')),
        )


class Combo(Recipe, Explanation, ScryfallLinkMixin):
    objects = models.Manager()
    recipes_prefetched = RecipePrefetchedManager()
    rename_prefetched = RenamePrefetchedManager()

    class Status(models.TextChoices):
        GENERATOR = 'G'
        UTILITY = 'U'
        DRAFT = 'D'
        NEEDS_REVIEW = 'NR'

    id: int
    uses: 'models.ManyToManyField[Card, CardInCombo]' = models.ManyToManyField(
        to=Card,
        through='CardInCombo',
        related_name='used_in_combos',
        help_text='Cards that this combo uses',
        blank=True,
        verbose_name='used cards',
    )
    cardincombo_set: models.Manager['CardInCombo']
    needs: 'models.ManyToManyField[Feature, FeatureNeededInCombo]' = models.ManyToManyField(
        to=Feature,
        through='FeatureNeededInCombo',
        related_name='needed_by_combos',
        help_text='Features that this combo needs',
        blank=True,
        verbose_name='needed features',
    )
    featureneededincombo_set: models.Manager['FeatureNeededInCombo']
    requires: 'models.ManyToManyField[Template, TemplateInCombo]' = models.ManyToManyField(
        to=Template,
        through='TemplateInCombo',
        related_name='required_by_combos',
        help_text='Templates that this combo requires',
        blank=True,
        verbose_name='required templates',
    )
    templateincombo_set: models.Manager['TemplateInCombo']
    produces: 'models.ManyToManyField[Feature, FeatureProducedInCombo]' = models.ManyToManyField(
        to=Feature,
        through='FeatureProducedInCombo',
        related_name='produced_by_combos',
        help_text='Features that this combo produces',
        verbose_name='produced features',
    )
    featureproducedincombo_set: models.Manager['FeatureProducedInCombo']
    removes: 'models.ManyToManyField[Feature, FeatureRemovedInCombo]' = models.ManyToManyField(
        to=Feature,
        through='FeatureRemovedInCombo',
        related_name='removed_by_combos',
        help_text='Features that this combo removes',
        blank=True,
        verbose_name='removed features',
    )
    featureremovedincombo_set: models.Manager['FeatureRemovedInCombo']
    status = models.CharField(choices=Status.choices, default=Status.DRAFT, help_text='Is this combo a generator for variants?', verbose_name='status', max_length=2)
    allow_many_cards = models.BooleanField(default=False, help_text=f'Allow variants to have more cards ({HIGHER_CARD_LIMIT}) than the default limit ({DEFAULT_CARD_LIMIT}). On the other hand, with this option enabled, the limit on the number of allowed variants is lowered to {LOWER_VARIANT_LIMIT}, instead of the default {DEFAULT_VARIANT_LIMIT}.')
    allow_multiple_copies = models.BooleanField(default=False, help_text='Allow variants to have more copies of the same card or template')
    variant_count = models.PositiveIntegerField(default=0, editable=False)
    public_variant_count = models.PositiveIntegerField(default=0, editable=False, help_text='Number of variants of this combo that are public')
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
        indexes = [
            models.Index(fields=['variant_count']),
            models.Index(fields=['public_variant_count']),
        ] + Explanation.text_trigram_indexes('combo')


class CardInCombo(ComboIngredient, WithUsedFace):
    id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.card} in combo {self.combo_id}'

    class Meta(ComboIngredient.Meta):
        unique_together = [('card', 'combo')]
        indexes = ComboIngredient.card_state_trigram_indexes('cic')


class TemplateInCombo(ComboIngredient):
    id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'{self.template} in combo {self.combo_id}'

    class Meta(ComboIngredient.Meta):
        unique_together = [('template', 'combo')]
        indexes = ComboIngredient.card_state_trigram_indexes('tic')


class FeatureNeededInCombo(ComboIngredient, WithFeatureAttributesMatcher):
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

    class Meta(ComboIngredient.Meta):
        indexes = ComboIngredient.card_state_trigram_indexes('fnic')


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
