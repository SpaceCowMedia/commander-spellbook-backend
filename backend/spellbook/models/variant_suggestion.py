from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from sortedm2m.fields import SortedManyToManyField
from .mixins import ScryfallLinkMixin
from .card import Card
from .template import Template
from .feature import Feature
from .variant import Variant
from .ingredient import IngredientInCombination
from .validators import TEXT_VALIDATORS, MANA_VALIDATOR, IDENTITY_VALIDATORS
from .utils import recipe


class VariantSuggestion(models.Model, ScryfallLinkMixin):
    class Status(models.TextChoices):
        NEW = 'N'
        ACCEPTED = 'A'
        REJECTED = 'R'

    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_variant_suggestions',
        help_text='Cards that this variant uses',
        blank=False,
        through='CardInVariantSuggestion')
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_variant_suggestions',
        help_text='Templates that this variant requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInVariantSuggestion')
    produces = SortedManyToManyField(
        to=Feature,
        related_name='produced_by_variant_suggestions',
        help_text='Features that this variant produces')
    variant_id = models.CharField(max_length=128, unique=True, blank=False, help_text='Unique ID for this variant suggestion', editable=False, error_messages={'unique': 'This combination of cards was already suggested.'})
    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Suggestion status for editors', max_length=2)
    mana_needed = models.CharField(blank=True, max_length=200, default='', help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, default='', help_text='Other prerequisites for this variant.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    identity = models.CharField(max_length=5, blank=False, null=False, help_text='Mana identity', verbose_name='mana identity', editable=False, validators=IDENTITY_VALIDATORS)
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='User that suggested this variant', related_name='variants')
    legal = models.BooleanField(blank=False, default=True, help_text='Is this variant legal in Commander?', verbose_name='is legal')
    spoiler = models.BooleanField(blank=False, default=False, help_text='Is this variant a spoiler?', verbose_name='is spoiler')

    class Meta:
        ordering = ['-status', '-created']
        verbose_name = 'variant suggestion'
        verbose_name_plural = 'variant suggestions'

    def cards(self):
        return self.uses.order_by('cardinvariantsuggestion')

    def templates(self):
        return self.requires.order_by('templateinvariantsuggestion')

    def __str__(self):
        if self.pk is None:
            return f'New variant suggestion with unique id <{self.id}>'
        produces = list(self.produces.all()[:4])
        return recipe([str(card) for card in self.cards()] + [str(template) for template in self.templates()], [str(feature) for feature in produces])

    def clean(self):
        if self.variant_id is None:
            raise ValidationError('Variant ID cannot be None')
        if self.variant_id == '':
            return
        if self.id is None:
            if VariantSuggestion.objects.filter(variant_id=self.variant_id).exists():
                raise ValidationError(f'This combination of cards was already suggested.')
            if Variant.objects.filter(id=self.variant_id).exists():
                raise ValidationError(f'This combination of cards is already a variant with id {self.variant_id}.')


class CardInVariantSuggestion(IngredientInCombination):
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.card} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'variant')]


class TemplateInVariantSuggestion(IngredientInCombination):
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.template} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'variant')]
