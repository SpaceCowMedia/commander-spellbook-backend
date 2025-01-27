from django.db import models
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .constants import MAX_CARD_NAME_LENGTH, MAX_FEATURE_NAME_LENGTH, MAX_MANA_NEEDED_LENGTH
from .mixins import PreSaveModelMixin
from .recipe import Recipe
from .card import Card
from .template import Template
from .variant import Variant
from .ingredient import IngredientInCombination
from .validators import TEXT_VALIDATORS, MANA_VALIDATOR, SCRYFALL_QUERY_HELP, SCRYFALL_QUERY_VALIDATOR, NAME_VALIDATORS, NOT_URL_VALIDATOR
from .scryfall import SCRYFALL_MAX_QUERY_LENGTH
from .utils import id_from_cards_and_templates_ids, simplify_card_name_on_database, simplify_card_name_with_spaces_on_database, strip_accents


class VariantSuggestion(Recipe):
    max_cards = 10
    max_templates = 5
    max_features = 100

    class Status(models.TextChoices):
        NEW = 'N'
        AWAITING_DISCUSSION = 'AD'
        PENDING_APPROVAL = 'PA'
        ACCEPTED = 'A'
        REJECTED = 'R'

    id: int
    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Suggestion status for editors', max_length=2)
    notes = models.TextField(blank=True, help_text='Notes written by editors', validators=TEXT_VALIDATORS)
    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=False, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    spoiler = models.BooleanField(default=False, help_text='Is this combo a spoiler?', verbose_name='is spoiler')
    comment = models.TextField(blank=True, max_length=2**10, help_text='Comment written by the user that suggested this combo', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='User that suggested this combo', related_name='suggestions')
    uses: models.Manager['CardUsedInVariantSuggestion']
    requires: models.Manager['TemplateRequiredInVariantSuggestion']
    produces: models.Manager['FeatureProducedInVariantSuggestion']

    class Meta:
        verbose_name = 'variant suggestion'
        verbose_name_plural = 'variant suggestions'
        default_manager_name = 'objects'
        ordering = [
            models.Case(
                *(models.When(status=s, then=models.Value(i)) for i, s in enumerate(('N', 'PA', 'AD', 'A', 'R'))),
                default=models.Value(10),
            ),
            'created',
        ]

    def cards(self) -> dict[str, int]:
        return {c.card: c.quantity for c in self.uses.all()}

    def templates(self) -> dict[str, int]:
        return {t.template: t.quantity for t in self.requires.all()}

    def features_produced(self) -> dict[str, int]:
        return {f.feature: 1 for f in self.produces.all()}

    @classmethod
    def validate(cls, cards: list[str], templates: list[str], produces: list[str], ignore=None):
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
        if ignore is not None:
            q = q.exclude(pk=ignore)
        for card in cards:
            q = q.filter(uses__card=card)
        for template in templates:
            q = q.filter(requires__template=template)
        if q.exists():
            raise ValidationError('This combo suggestion is redundant. Another suggestion with the same cards and templates already exists.')


class CardUsedInVariantSuggestion(PreSaveModelMixin, IngredientInCombination):
    card = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=False, help_text='Card name', verbose_name='card name', validators=[NOT_URL_VALIDATOR])
    card_unaccented = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, editable=False)
    card_unaccented_simplified = models.GeneratedField(
        db_persist=True,
        expression=simplify_card_name_on_database('card_unaccented'),
        output_field=models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, editable=False),
    )
    card_unaccented_simplified_with_spaces = models.GeneratedField(
        db_persist=True,
        expression=simplify_card_name_with_spaces_on_database('card_unaccented'),
        output_field=models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, editable=False),
    )
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='uses')

    def __str__(self):
        return self.card

    class Meta(IngredientInCombination.Meta):
        pass

    def pre_save(self):
        self.card_unaccented = strip_accents(self.card)


class TemplateRequiredInVariantSuggestion(IngredientInCombination):
    template = models.CharField(max_length=Template.MAX_TEMPLATE_NAME_LENGTH, blank=False, help_text='Template name', verbose_name='template name', validators=NAME_VALIDATORS)
    scryfall_query = models.CharField(max_length=SCRYFALL_MAX_QUERY_LENGTH, blank=True, null=True, verbose_name='Scryfall query', help_text=SCRYFALL_QUERY_HELP, validators=[SCRYFALL_QUERY_VALIDATOR])
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='requires')

    def __str__(self):
        return self.template

    class Meta(IngredientInCombination.Meta):
        pass


class FeatureProducedInVariantSuggestion(models.Model):
    feature = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, blank=False, help_text='Feature name', verbose_name='feature name', validators=NAME_VALIDATORS)
    variant = models.ForeignKey(to=VariantSuggestion, on_delete=models.CASCADE, related_name='produces')

    def __str__(self):
        return self.feature

    class Meta:
        ordering = ['feature', 'id']


@receiver([post_save, post_delete], sender=CardUsedInVariantSuggestion, dispatch_uid='card_used_in_variant_suggestion_saved')
@receiver([post_save, post_delete], sender=TemplateRequiredInVariantSuggestion, dispatch_uid='template_required_in_variant_suggestion_saved')
@receiver([post_save, post_delete], sender=FeatureProducedInVariantSuggestion, dispatch_uid='feature_produced_in_variant_suggestion_saved')
def update_variant_suggestion_name(
    sender,
    instance: CardUsedInVariantSuggestion | TemplateRequiredInVariantSuggestion | FeatureProducedInVariantSuggestion,
    raw=False,
    **kwargs,
):
    if raw:
        return
    variant_suggestion = instance.variant
    variant_suggestion.update_recipe_from_data()
    variant_suggestion.save()
