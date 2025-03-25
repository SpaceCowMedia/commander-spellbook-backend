from dataclasses import dataclass
import re
from typing import Iterable, Sequence
from django.db import models, connection
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.utils.html import format_html
from django.db.models.functions import Upper
from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from .playable import Playable
from .recipe import Recipe
from .mixins import ScryfallLinkMixin, PreSaveSerializedModelMixin, PreSaveSerializedManager
from .card import Card
from .template import Template
from .feature import Feature
from .ingredient import IngredientInCombination, ZoneLocation
from .combo import Combo
from .job import Job
from .validators import TEXT_VALIDATORS, MANA_VALIDATOR
from .utils import CardType, mana_value, merge_identities
from .constants import MAX_MANA_NEEDED_LENGTH


class RecipePrefetchedManager(PreSaveSerializedManager):
    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'cardinvariant_set',
            'cardinvariant_set__card',
            'templateinvariant_set',
            'templateinvariant_set__template',
            'featureproducedbyvariant_set',
            'featureproducedbyvariant_set__feature',
        )


DEFAULT_VIEW_ORDERING = (models.F('popularity').desc(nulls_last=True), models.F('identity_count').asc(), models.F('card_count').asc(), models.F('created').desc(), models.F('id'))


class Variant(Recipe, Playable, PreSaveSerializedModelMixin, ScryfallLinkMixin):
    objects: PreSaveSerializedManager
    recipes_prefetched = RecipePrefetchedManager()

    class Status(models.TextChoices):
        NEW = 'N'
        DRAFT = 'D'
        NEEDS_REVIEW = 'NR'
        OK = 'OK'
        EXAMPLE = 'E'
        RESTORE = 'R'
        NOT_WORKING = 'NW'

    class BracketTag(models.TextChoices):
        RUTHLESS = 'R'
        SPICY = 'S'
        POWERFUL = 'P'
        ODDBALL = 'O'
        PRECON_APPROPRIATE = 'PA'
        CASUAL = 'C'

    @classmethod
    def public_statuses(cls):
        return (cls.Status.OK, cls.Status.EXAMPLE)

    @classmethod
    def preview_statuses(cls):
        return (cls.Status.DRAFT, cls.Status.NEEDS_REVIEW)

    id = models.CharField(max_length=128, primary_key=True, help_text='Unique ID for this variant', verbose_name='ID')
    uses = models.ManyToManyField(
        to=Card,
        through='CardInVariant',
        related_name='used_in_variants',
        help_text='Cards that this variant uses',
        editable=False,
    )
    cardinvariant_set: models.Manager['CardInVariant']
    requires = models.ManyToManyField(
        to=Template,
        through='TemplateInVariant',
        related_name='required_by_variants',
        help_text='Templates that this variant requires',
        blank=True,
        verbose_name='required templates',
    )
    templateinvariant_set: models.Manager['TemplateInVariant']
    produces = models.ManyToManyField(
        to=Feature,
        through='FeatureProducedByVariant',
        related_name='produced_by_variants',
        help_text='Features that this variant produces',
        editable=False,
    )
    featureproducedbyvariant_set: models.Manager['FeatureProducedByVariant']
    includes = models.ManyToManyField(
        to=Combo,
        through='VariantIncludesCombo',
        related_name='included_in_variants',
        help_text='Combo that this variant includes',
        editable=False,
    )
    variantincludescombo_set: models.Manager['VariantIncludesCombo']
    of = models.ManyToManyField(
        to=Combo,
        through='VariantOfCombo',
        related_name='variants',
        help_text='Combo that this variant is an instance of',
        editable=False,
    )
    variantofcombo_set: models.Manager['VariantOfCombo']
    status = models.CharField(choices=Status.choices, db_default=Status.NEW, max_length=2, help_text='Variant status for editors')
    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    mana_value_needed = models.PositiveIntegerField(editable=False, help_text='Mana value needed for this combo. Calculated from mana_needed.')
    easy_prerequisites = models.TextField(blank=True, help_text='Easily achievable prerequisites for this combo.', validators=TEXT_VALIDATORS)
    notable_prerequisites = models.TextField(blank=True, help_text='Notable prerequisites for this combo.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    notes = models.TextField(blank=True, help_text='Notes about the combo', validators=TEXT_VALIDATORS)
    public_notes = models.TextField(blank=True, help_text='Notes about the combo that will be displayed on the site', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    generated_by = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='Job that generated this variant', related_name='variants')
    popularity = models.PositiveIntegerField(db_default=None, null=True, editable=False, help_text='Popularity of this variant, provided by EDHREC')
    description_line_count = models.PositiveIntegerField(editable=False, help_text='Number of lines in the description')
    prerequisites_line_count = models.PositiveIntegerField(editable=False, help_text='Number of lines in the other prerequisites')
    published = models.BooleanField(editable=False, default=False, help_text='Whether the variant has been published')
    variant_count = models.PositiveIntegerField(editable=False, default=0, help_text='Number of variants generated by the same generator combos')
    hulkline = models.BooleanField(editable=False, default=False, help_text='Whether the variant is a Protean Hulk line')
    bracket_tag = models.CharField(choices=BracketTag.choices, default=BracketTag.RUTHLESS, max_length=2, blank=False, editable=False, help_text='Bracket tag for this variant')
    bracket_tag_override = models.CharField(choices=BracketTag.choices, max_length=2, blank=True, null=True, help_text='Override bracket tag for this variant')
    bracket = models.GeneratedField(
        db_persist=True,
        expression=models.Case(
            models.When(bracket_tag_override=BracketTag.RUTHLESS, then=models.Value(4)),
            models.When(bracket_tag_override=BracketTag.SPICY, then=models.Value(3)),
            models.When(bracket_tag_override=BracketTag.POWERFUL, then=models.Value(3)),
            models.When(bracket_tag_override=BracketTag.ODDBALL, then=models.Value(2)),
            models.When(bracket_tag_override=BracketTag.PRECON_APPROPRIATE, then=models.Value(2)),
            models.When(bracket_tag_override=BracketTag.CASUAL, then=models.Value(1)),
            models.When(bracket_tag=BracketTag.RUTHLESS, then=models.Value(4)),
            models.When(bracket_tag=BracketTag.SPICY, then=models.Value(3)),
            models.When(bracket_tag=BracketTag.POWERFUL, then=models.Value(3)),
            models.When(bracket_tag=BracketTag.ODDBALL, then=models.Value(2)),
            models.When(bracket_tag=BracketTag.PRECON_APPROPRIATE, then=models.Value(2)),
            models.When(bracket_tag=BracketTag.CASUAL, then=models.Value(1)),
            default=models.Value(0),
        ),
        output_field=models.PositiveSmallIntegerField(help_text='Bracket number based on the tag'),
    )

    @classmethod
    def computed_fields(cls):
        '''
        Returns the fields that are computed from related models.
        '''
        return Playable.playable_fields() + [
            'hulkline',
            'bracket_tag',
            'mana_value_needed',
        ]

    class Meta:
        verbose_name = 'variant'
        verbose_name_plural = 'variants'
        default_manager_name = 'objects'
        ordering = [
            models.Case(
                models.When(status='N', then=models.Value(0)),
                models.When(status='D', then=models.Value(1)),
                models.When(status='OK', then=models.Value(2)),
                models.When(status='E', then=models.Value(3)),
                models.When(status='R', then=models.Value(4)),
                models.When(status='NW', then=models.Value(5)),
                default=models.Value(10),
            ),
            '-created'
        ]
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['-created']),
            models.Index(fields=['-updated']),
            models.Index(fields=['prerequisites_line_count']),
            models.Index(fields=['description_line_count']),
            *(models.Index(fields=[field]) for field in Playable.playable_fields()),
            *(models.Index(fields=[f'identity_{color}']) for color in 'wubrg'),
        ] + ([
            models.Index(*DEFAULT_VIEW_ORDERING, name='variant_view_ordering_idx'),
            models.Index(*('identity_count',) + DEFAULT_VIEW_ORDERING, name='variant_ic_view_ordering_idx'),
            models.Index(*('variant_count',) + DEFAULT_VIEW_ORDERING, name='variant_vc_view_ordering_idx'),
            models.Index(*('card_count',) + DEFAULT_VIEW_ORDERING, name='variant_cc_view_ordering_idx'),
            GinIndex(OpClass(Upper('easy_prerequisites'), name='gin_trgm_ops'), name='variant_easy_prereq_trgm_idx'),
            GinIndex(OpClass(Upper('notable_prerequisites'), name='gin_trgm_ops'), name='variant_notabl_prereq_trgm_idx'),
            GinIndex(OpClass(Upper('description'), name='gin_trgm_ops'), name='variant_description_trgm_idx'),
        ] if connection.vendor == 'postgresql' else [])

    def cards(self) -> dict[str, int]:
        return {c.card.name: c.quantity for c in self.cardinvariant_set.all()}

    def templates(self) -> dict[str, int]:
        return {t.template.name: t.quantity for t in self.templateinvariant_set.all()}

    def features_produced(self) -> dict[str, int]:
        return {f.feature.name: 1 for f in self.featureproducedbyvariant_set.all()}

    def pre_save(self):
        self.mana_value_needed = mana_value(self.mana_needed)
        self.description_line_count = self.description.count('\n') + 1 if self.description else 0
        self.prerequisites_line_count = (
            self.easy_prerequisites.count('\n') + 1 if self.easy_prerequisites else 0
        ) + (
            self.notable_prerequisites.count('\n') + 1 if self.notable_prerequisites else 0
        )

    @dataclass(frozen=True)
    class Recipe:
        cards: list[tuple['CardInVariant', Card]]
        templates: list[tuple['TemplateInVariant', Template]]
        features: list[tuple['FeatureProducedByVariant', Feature]]

    def update_variant(self):
        return self.update_variant_from_recipe(self.get_recipe())

    def get_recipe(self) -> Recipe:
        cards: dict[int, Card] = {c.id: c for c in self.uses.all()}
        civs = [(civ, cards[civ.card_id]) for civ in self.cardinvariant_set.all()]
        templates: dict[int, Template] = {t.id: t for t in self.requires.all()}
        tivs = [(tiv, templates[tiv.template_id]) for tiv in self.templateinvariant_set.all()]
        features: dict[int, Feature] = {f.id: f for f in self.produces.all()}
        fpbvs = [(fp, features[fp.feature_id]) for fp in self.featureproducedbyvariant_set.all()]
        return Variant.Recipe(civs, tivs, fpbvs)

    def update_variant_from_recipe(
            self,
            recipe: Recipe,
    ) -> bool:
        requires_commander = any(civ.must_be_commander for civ, _ in recipe.cards) or any(tiv.must_be_commander for tiv, _ in recipe.templates)
        old_values = {field: getattr(self, field) for field in self.computed_fields()}
        self.mana_value_needed = mana_value(self.mana_needed)
        self.update_playable_fields([card for _, card in recipe.cards], requires_commander=requires_commander)
        battlefield_mana_value = sum(card.mana_value for civ, card in recipe.cards if ZoneLocation.BATTLEFIELD in civ.zone_locations)
        self.hulkline = \
            battlefield_mana_value <= 6 \
            and not requires_commander \
            and all(
                CardType.CREATURE in card.type_line and (ZoneLocation.BATTLEFIELD in civ.zone_locations and not civ.battlefield_card_state or ZoneLocation.LIBRARY in civ.zone_locations and not civ.library_card_state)
                for civ, card in recipe.cards
            ) \
            and all(
                'creature' in template.name.lower() and 'non-creature' not in template.name.lower() and (ZoneLocation.BATTLEFIELD in tiv.zone_locations and not tiv.battlefield_card_state or ZoneLocation.LIBRARY in tiv.zone_locations and not tiv.library_card_state)
                for tiv, template in recipe.templates
            ) \
            and (
                battlefield_mana_value <= 4 or all(name.split(',', 1)[0] not in self.notable_prerequisites for _, card in recipe.cards for name in card.name.split(' // '))
            )
        self.bracket_tag = estimate_bracket([card for _, card in recipe.cards], [template for _, template in recipe.templates], included_variants=[(self, recipe)]).bracket_tag
        new_values = {field: getattr(self, field) for field in self.computed_fields()}
        return old_values != new_values

    def update_playable_fields(self, cards: Iterable['Card'], requires_commander: bool) -> bool:
        '''Returns True if any field was changed, False otherwise.'''
        cards = list(cards)
        old_values = {field: getattr(self, field) for field in self.playable_fields()}
        self.mana_value = sum(card.mana_value for card in cards)
        self.identity = merge_identities(playable.identity for playable in cards)
        self.spoiler = any(playable.spoiler for playable in cards)
        self.legal_commander = all(playable.legal_commander for playable in cards)
        self.legal_pauper_commander_main = all(playable.legal_pauper_commander_main for playable in cards)
        pauper_commanders = [playable for playable in cards if not playable.legal_pauper_commander_main]
        pauper_commanders_identity = merge_identities(playable.identity for playable in pauper_commanders)
        self.legal_pauper_commander = all(playable.legal_pauper_commander for playable in cards) and (
            len(pauper_commanders) == 0 or self.identity == pauper_commanders_identity and (
                len(pauper_commanders) == 1 or (
                    len(pauper_commanders) == 2 and all('Partner' in playable.keywords for playable in pauper_commanders)
                )
            )
        )
        self.legal_oathbreaker = all(playable.legal_oathbreaker for playable in cards)
        self.legal_predh = all(playable.legal_predh for playable in cards)
        self.legal_brawl = all(playable.legal_brawl for playable in cards)
        self.legal_vintage = not requires_commander and all(playable.legal_vintage for playable in cards)
        self.legal_legacy = not requires_commander and all(playable.legal_legacy for playable in cards)
        self.legal_premodern = not requires_commander and all(playable.legal_premodern for playable in cards)
        self.legal_modern = not requires_commander and all(playable.legal_modern for playable in cards)
        self.legal_pioneer = not requires_commander and all(playable.legal_pioneer for playable in cards)
        self.legal_standard = not requires_commander and all(playable.legal_standard for playable in cards)
        self.legal_pauper = not requires_commander and all(playable.legal_pauper for playable in cards)
        self.price_tcgplayer = sum(playable.price_tcgplayer for playable in cards)
        self.price_cardkingdom = sum(playable.price_cardkingdom for playable in cards)
        self.price_cardmarket = sum(playable.price_cardmarket for playable in cards)
        new_values = {field: getattr(self, field) for field in self.playable_fields()}
        return old_values != new_values

    def spellbook_link(self, raw=False):
        path = f'combo/{self.id}'
        link = 'https://commanderspellbook.com/' + path
        if raw:
            return link
        text = 'Show combo on Commander Spellbook'
        if self.status not in Variant.public_statuses():
            if self.status in Variant.preview_statuses():
                text = 'Show combo preview on Commander Spellbook (remember to login to see it)'
            else:
                return None
        return format_html('<a href="{}" target="_blank">{}</a>', link, text)


class CardInVariant(IngredientInCombination):
    id: int
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)
    variant_id: str

    def __str__(self):
        return f'{self.card} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'variant')]


class TemplateInVariant(IngredientInCombination):
    id: int
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    template_id: int
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)
    variant_id: str

    def __str__(self):
        return f'{self.template} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'variant')]


class FeatureProducedByVariant(models.Model):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)
    variant_id: str
    quantity = models.PositiveSmallIntegerField(default=1, blank=False, help_text='Quantity of the feature produced by the variant.', verbose_name='quantity', validators=[MinValueValidator(1)])

    def __str__(self):
        return f'{self.feature} produced by {self.variant.pk}'

    class Meta:
        unique_together = [('feature', 'variant')]

    def clean(self):
        super().clean()
        if self.quantity > 1 and self.feature.uncountable:
            raise ValidationError('Uncountable features can only appear in one copy.')


class VariantOfCombo(models.Model):
    id: int
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)
    variant_id: str
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'Variant {self.variant.pk} of {self.combo_id}'

    class Meta:
        unique_together = [('variant', 'combo')]


class VariantIncludesCombo(models.Model):
    id: int
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)
    variant_id: str
    combo = models.ForeignKey(to=Combo, on_delete=models.CASCADE)
    combo_id: int

    def __str__(self):
        return f'Variant {self.variant.pk} includes {self.combo_id}'

    class Meta:
        unique_together = [('variant', 'combo')]


@receiver(post_save, sender=Variant.uses.through, dispatch_uid='update_variant_on_cards')
@receiver(post_save, sender=Variant.requires.through, dispatch_uid='update_variant_on_templates')
def update_variant_on_ingredient(sender, instance: CardInVariant | TemplateInVariant, raw=False, **kwargs):
    if raw:
        return
    variant = instance.variant
    variant.update_variant()
    variant.update_recipe_from_data()
    variant.save()


@receiver(pre_delete, sender=Combo, dispatch_uid='combo_deleted')
def combo_delete(sender, instance: Combo, **kwargs) -> None:
    Variant.objects.alias(
        of_count=models.Count('of', distinct=True),
    ).filter(
        of_count=1,
        of=instance,
    ).update(
        status=Variant.Status.RESTORE,
    )


@dataclass(frozen=True)
class BracketEstimateData:
    game_changer_cards: list[Card]
    mass_land_denial_cards: list[Card]
    mass_land_denial_templates: list[Template]
    mass_land_denial_combos: list[Variant]
    extra_turn_cards: list[Card]
    extra_turn_templates: list[Template]
    extra_turns_combos: list[Variant]
    tutor_cards: list[Card]
    tutor_templates: list[Template]
    lock_combos: list[Variant]
    skip_turns_combos: list[Variant]
    definitely_early_game_two_card_combos: list[Variant]
    arguably_early_game_two_card_combos: list[Variant]
    definitely_late_game_two_card_combos: list[Variant]
    borderline_late_game_two_card_combos: list[Variant]


@dataclass(frozen=True)
class BracketEstimate:
    bracket_tag: Variant.BracketTag
    data: BracketEstimateData


def estimate_bracket(cards: Sequence[Card], templates: Sequence[Template], included_variants: Sequence[tuple[Variant, Variant.Recipe]]) -> BracketEstimate:
    def _data() -> BracketEstimateData:
        definitely_early_game_two_card_combos: list[Variant] = []
        arguably_early_game_two_card_combos: list[Variant] = []
        definitely_late_game_two_card_combos: list[Variant] = []
        borderline_late_game_two_card_combos: list[Variant] = []

        for variant, recipe in included_variants:
            arguably_two_card = sum(
                civ.quantity
                for civ, _ in recipe.cards
                if ZoneLocation.LIBRARY not in civ.zone_locations and ZoneLocation.COMMAND_ZONE not in civ.zone_locations
            ) + sum(
                tiv.quantity
                for tiv, _ in recipe.templates
                if ZoneLocation.LIBRARY not in tiv.zone_locations and ZoneLocation.COMMAND_ZONE not in tiv.zone_locations
            ) <= 2
            no_extra_card_prerequisites = not variant.notable_prerequisites
            definitely_two_card = arguably_two_card and no_extra_card_prerequisites
            relevant = any(feature.status in (Feature.Status.STANDALONE,) for _, feature in recipe.features)
            borderline_relevant = any(feature.status in (Feature.Status.STANDALONE, Feature.Status.CONTEXTUAL) for _, feature in recipe.features)
            definitely_early_game = variant.mana_value_needed <= 4
            arguably_early_game = variant.mana_value_needed <= 5
            if relevant and definitely_two_card and definitely_early_game:
                definitely_early_game_two_card_combos.append(variant)
            elif relevant and arguably_two_card and arguably_early_game:
                arguably_early_game_two_card_combos.append(variant)
            elif relevant and definitely_two_card and not arguably_early_game:
                definitely_late_game_two_card_combos.append(variant)
            elif borderline_relevant and arguably_two_card and not arguably_early_game:
                borderline_late_game_two_card_combos.append(variant)

        extra_turns_combos = [
            v
            for v, recipe in included_variants
            if any(
                re.search(r'(?:near-)?infinite (?:extra )?turns?', feature.name, re.IGNORECASE)
                for _, feature in recipe.features
            )
        ]
        mass_land_denial_combos = [
            v
            for v, recipe in included_variants
            if any(
                re.search(r'mass land (?:destruction|denial)', feature.name, re.IGNORECASE)
                for _, feature in recipe.features
            )
        ]
        lock_combos = [
            v
            for v, recipe in included_variants
            if any(
                feature.name.lower() == 'lock'
                for _, feature in recipe.features
            )
        ]
        skip_turns_combos = [
            v
            for v, recipe in included_variants
            if any(
                re.search(r'(?:infinite(?:ly)? )?skip (?:(?:all )?(?:your )|infinite )?(?:future )?turns?', feature.name, re.IGNORECASE)
                for _, feature in recipe.features
            )
        ]
        return BracketEstimateData(
            game_changer_cards=[c for c in cards if c.game_changer],
            mass_land_denial_cards=[c for c in cards if c.mass_land_denial],
            mass_land_denial_templates=[t for t in templates if any(term in t.name.lower() for term in ('mass land destruction', 'mass land denial'))],
            extra_turn_cards=[c for c in cards if c.extra_turn],
            extra_turn_templates=[t for t in templates if any(term in t.name.lower() for term in ('extra turn',))],
            tutor_cards=[c for c in cards if c.tutor],
            tutor_templates=[t for t in templates if any(term in t.name.lower() for term in ('tutor',))],
            mass_land_denial_combos=mass_land_denial_combos,
            extra_turns_combos=extra_turns_combos,
            lock_combos=lock_combos,
            skip_turns_combos=skip_turns_combos,
            definitely_early_game_two_card_combos=definitely_early_game_two_card_combos,
            arguably_early_game_two_card_combos=arguably_early_game_two_card_combos,
            definitely_late_game_two_card_combos=definitely_late_game_two_card_combos,
            borderline_late_game_two_card_combos=borderline_late_game_two_card_combos,
        )

    data = _data()

    if any((
        data.definitely_early_game_two_card_combos,
        len(data.extra_turn_cards) >= 2,
        data.extra_turns_combos,
        data.mass_land_denial_cards,
        data.mass_land_denial_templates,
        data.mass_land_denial_combos,
        len(data.game_changer_cards) >= 4,
    )):
        bracket = Variant.BracketTag.RUTHLESS
    elif any((
        data.arguably_early_game_two_card_combos,
        data.lock_combos,
        data.skip_turns_combos,
    )):
        bracket = Variant.BracketTag.SPICY
    elif any((
        data.definitely_late_game_two_card_combos,
        data.game_changer_cards,
        len(data.tutor_cards) >= 3,
        len(data.tutor_templates) >= 3,
    )):
        bracket = Variant.BracketTag.POWERFUL
    elif any((
        data.borderline_late_game_two_card_combos,
    )):
        bracket = Variant.BracketTag.ODDBALL
    elif any((
        data.extra_turn_cards,
        data.extra_turn_templates,
    )):
        bracket = Variant.BracketTag.PRECON_APPROPRIATE
    else:
        bracket = Variant.BracketTag.CASUAL

    return BracketEstimate(
        bracket_tag=bracket,
        data=data,
    )
