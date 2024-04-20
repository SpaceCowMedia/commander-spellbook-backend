from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH
from .card import Card
from .feature import Feature
from .template import Template
from .variant import Variant
from .ingredient import IngredientInCombination, Recipe
from .validators import TEXT_VALIDATORS, MANA_VALIDATOR, SCRYFALL_QUERY_HELP, SCRYFALL_QUERY_VALIDATOR, NAME_VALIDATORS, NOT_URL_VALIDATOR
from .scryfall import SCRYFALL_MAX_QUERY_LENGTH
from .utils import id_from_cards_and_templates_ids


class VariantSuggestion(Recipe):
    max_cards = 10
    max_templates = 5
    max_features = 100

    class Status(models.TextChoices):
        NEW = 'N'
        NEEDS_REVIEW = 'NR'
        ACCEPTED = 'A'
        REJECTED = 'R'

    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Suggestion status for editors', max_length=2)
    notes = models.TextField(blank=True, help_text='Notes written by editors', validators=TEXT_VALIDATORS)
    mana_needed = models.CharField(blank=True, max_length=200, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=False, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    spoiler = models.BooleanField(default=False, help_text='Is this combo a spoiler?', verbose_name='is spoiler')
    comment = models.TextField(blank=True, max_length=2**10, help_text='Comment written by the user that suggested this combo', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='User that suggested this combo', related_name='suggestions')

    class Meta:
        verbose_name = 'variant suggestion'
        verbose_name_plural = 'variant suggestions'
        default_manager_name = 'objects'
        ordering = [
            models.Case(
                models.When(status='N', then=models.Value(0)),
                models.When(status='NR', then=models.Value(1)),
                models.When(status='A', then=models.Value(2)),
                models.When(status='R', then=models.Value(3)),
                default=models.Value(10),
            ),
            'created'
        ]

    def cards(self) -> list[Card]:
        return list(self.uses.all())  # type: ignore

    def templates(self) -> list[Template]:
        return list(self.requires.all())  # type: ignore

    def features_produced(self) -> list[Feature]:
        return list(self.produces.all())  # type: ignore

    @classmethod
    def validate(cls, cards: list[str], templates: list[str], produces: list[str]):
        if len(cards) == 0:
            raise ValidationError('You must specify at least one card.')
        if len(produces) == 0:
            raise ValidationError('You must specify at least one feature.')
        if len(cards) > cls.max_cards:
            raise ValidationError(f'You cannot specify more than {cls.max_cards} cards.')
        if len(templates) > cls.max_templates:
            raise ValidationError(f'You cannot specify more than {cls.max_templates} templates.')
        if len(produces) > cls.max_features:
            raise ValidationError(f'You cannot specify more than {cls.max_features} features.')
        unique_card_names = {card.lower() for card in cards}
        if len(unique_card_names) != len(cards):
            raise ValidationError('You cannot specify the same card more than once.')
        unique_template_names = {template.lower() for template in templates}
        if len(unique_template_names) != len(templates):
            raise ValidationError('You cannot specify the same template more than once.')
        unique_feature_names = {feature.lower() for feature in produces}
        if len(unique_feature_names) != len(produces):
            raise ValidationError('You cannot specify the same feature more than once.')
        card_entities = list(Card.objects.filter(name__in=cards))
        template_entities = list(Template.objects.filter(name__in=templates))
        if len(card_entities) == len(cards) and len(template_entities) == len(templates):
            variant_id = id_from_cards_and_templates_ids([card.id for card in card_entities], [template.id for template in template_entities])
            if Variant.objects.filter(id=variant_id).exists():
                raise ValidationError('This combo already exists.')
        q = VariantSuggestion.objects \
            .annotate(
                uses_count=models.Count('uses', distinct=True),
                requires_count=models.Count('requires', distinct=True)) \
            .filter(
                uses_count=len(cards),
                requires_count=len(templates))
        for card in cards:
            q = q.filter(uses__card=card)
        for template in templates:
            q = q.filter(requires__template=template)
        if q.exists():
            raise ValidationError('This combo suggestion is redundant. Another suggestion with the same cards and templates already exists.')


class CardUsedInVariantSuggestion(IngredientInCombination):
    card = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=False, help_text='Card name', verbose_name='card name', validators=[NOT_URL_VALIDATOR])
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='uses')

    def __str__(self):
        return self.card

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'variant')]


class TemplateRequiredInVariantSuggestion(IngredientInCombination):
    template = models.CharField(max_length=Template.MAX_TEMPLATE_NAME_LENGTH, blank=False, help_text='Template name', verbose_name='template name', validators=NAME_VALIDATORS)
    scryfall_query = models.CharField(max_length=SCRYFALL_MAX_QUERY_LENGTH, blank=True, null=True, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=[SCRYFALL_QUERY_VALIDATOR])
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='requires')

    def __str__(self):
        return self.template

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'variant')]


class FeatureProducedInVariantSuggestion(models.Model):
    feature = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, blank=False, help_text='Feature name', verbose_name='feature name', validators=NAME_VALIDATORS)
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='produces')

    def __str__(self):
        return self.feature

    class Meta:
        unique_together = [('feature', 'variant')]
        ordering = ['feature', 'id']


@receiver([post_save, post_delete], sender=CardUsedInVariantSuggestion, dispatch_uid='card_used_in_variant_suggestion_saved')
@receiver([post_save, post_delete], sender=TemplateRequiredInVariantSuggestion, dispatch_uid='template_required_in_variant_suggestion_saved')
@receiver([post_save, post_delete], sender=FeatureProducedInVariantSuggestion, dispatch_uid='feature_produced_in_variant_suggestion_saved')
def update_variant_suggestion_name(sender, instance, **kwargs):
    variant_suggestion = instance.variant
    variant_suggestion.name = variant_suggestion._str()
    variant_suggestion.save()
