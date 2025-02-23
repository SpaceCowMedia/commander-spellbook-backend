from dataclasses import dataclass
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
from .utils import CardType, chain_strings, mana_value, merge_identities
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
    status = models.CharField(choices=Status.choices, db_default=Status.NEW, help_text='Variant status for editors', max_length=2)
    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    mana_value_needed = models.PositiveIntegerField(editable=False, help_text='Mana value needed for this combo. Calculated from mana_needed.')
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this variant.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    notes = models.TextField(blank=True, help_text='Notes about the combo', validators=TEXT_VALIDATORS)
    public_notes = models.TextField(blank=True, help_text='Notes about the combo that will be displayed on the site', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    generated_by = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='Job that generated this variant', related_name='variants')
    popularity = models.PositiveIntegerField(db_default=None, null=True, editable=False, help_text='Popularity of this variant, provided by EDHREC')
    description_line_count = models.PositiveIntegerField(editable=False, help_text='Number of lines in the description')
    other_prerequisites_line_count = models.PositiveIntegerField(editable=False, help_text='Number of lines in the other prerequisites')
    published = models.BooleanField(editable=False, default=False, help_text='Whether the variant has been published')
    variant_count = models.PositiveIntegerField(editable=False, default=0, help_text='Number of variants generated by the same generator combos')
    hulkline = models.BooleanField(editable=False, default=False, help_text='Whether the variant is a Protean Hulk line')
    complete = models.BooleanField(editable=False, default=False, help_text='Whether the variant is complete')
    bracket = models.PositiveSmallIntegerField(editable=False, default=4, help_text='Suggested bracket for this variant')

    @classmethod
    def computed_fields(cls):
        '''
        Returns the fields that are computed from related models.
        '''
        return Playable.playable_fields() + [
            'hulkline',
            'complete',
            'bracket',
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
            models.Index(fields=('-created',)),
            models.Index(fields=('-updated',)),
            models.Index(fields=['other_prerequisites_line_count']),
            models.Index(fields=['description_line_count']),
            *(models.Index(fields=[field]) for field in Playable.playable_fields()),
            *(models.Index(fields=[f'identity_{color}']) for color in 'wubrg'),
            models.Index(fields=['complete']),
        ] + ([
            models.Index(*DEFAULT_VIEW_ORDERING, name='variant_view_ordering_idx'),
            models.Index(*('identity_count',) + DEFAULT_VIEW_ORDERING, name='variant_ic_view_ordering_idx'),
            models.Index(*('variant_count',) + DEFAULT_VIEW_ORDERING, name='variant_vc_view_ordering_idx'),
            models.Index(*('card_count',) + DEFAULT_VIEW_ORDERING, name='variant_cc_view_ordering_idx'),
            GinIndex(OpClass(Upper('other_prerequisites'), name='gin_trgm_ops'), name='variant_other_prereq_trgm_idx'),
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
        self.other_prerequisites_line_count = self.other_prerequisites.count('\n') + 1 if self.other_prerequisites else 0

    def update_variant(self):
        cards: dict[int, Card] = {c.id: c for c in self.uses.all()}
        civs = [(civ, cards[civ.card_id]) for civ in self.cardinvariant_set.all()]
        templates: dict[int, Template] = {t.id: t for t in self.requires.all()}
        tivs = [(tiv, templates[tiv.template_id]) for tiv in self.templateinvariant_set.all()]
        features: dict[int, Feature] = {f.id: f for f in self.produces.all()}
        fpbvs = [(fp, features[fp.feature_id]) for fp in self.featureproducedbyvariant_set.all()]
        return self.update_variant_from_ingredients(civs, tivs, fpbvs)

    def update_variant_from_ingredients(
            self,
            cards: Sequence[tuple['CardInVariant', Card]],
            templates: Sequence[tuple['TemplateInVariant', Template]],
            features: Sequence[tuple['FeatureProducedByVariant', Feature]],
    ) -> bool:
        requires_commander = any(civ.must_be_commander for civ, _ in cards) or any(tiv.must_be_commander for tiv, _ in templates)
        old_values = {field: getattr(self, field) for field in self.computed_fields()}
        self.update_playable_fields([card for _, card in cards], requires_commander=requires_commander)
        self.hulkline = \
            not requires_commander \
            and all(
                CardType.CREATURE in card.type_line and ZoneLocation.BATTLEFIELD in civ.zone_locations and not civ.battlefield_card_state
                for civ, card in cards
            ) \
            and self.mana_value <= 6
        self.complete = any(f.relevant for _, f in features)
        self.bracket = estimate_bracket([card for _, card in cards], [template for _, template in templates], included_variants=[self], single=True).bracket
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
        self.legal_pauper_commander = all(playable.legal_pauper_commander for playable in cards) and (
            len(pauper_commanders) == 1 or (
                len(pauper_commanders) == 2 and all('Partner' in playable.keywords for playable in pauper_commanders)
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
class BracketEstimate:
    bracket: int
    explanation: str
    game_changers: list[Card]
    mass_land_denial: list[Card]
    mass_land_denial_templates: list[Template]
    extra_turn: list[Card]
    extra_turn_templates: list[Template]
    tutor: list[Card]
    tutor_templates: list[Template]
    two_card_combos: list[Variant]
    early_game_two_card_combos: list[Variant]


def estimate_bracket(cards: Sequence[Card], templates: Sequence[Template], included_variants: Sequence[Variant], single: bool) -> BracketEstimate:
    game_changers = [c for c in cards if c.game_changer]
    mass_land_denial = [c for c in cards if c.mass_land_destruction]
    mass_land_denial_templates = [t for t in templates if any(term in t.name.lower() for term in ('mass land destruction', 'mass land denial'))]
    total_mass_land_denial_count = len(mass_land_denial) + len(mass_land_denial_templates)
    extra_turn = [c for c in cards if c.extra_turn]
    extra_turn_templates = [t for t in templates if any(term in t.name.lower() for term in ('extra turn',))]
    total_extra_turn_count = len(extra_turn) + len(extra_turn_templates)
    tutor = [c for c in cards if c.tutor]
    tutor_templates = [t for t in templates if any(term in t.name.lower() for term in ('tutor',))]
    total_tutor_count = len(tutor) + len(tutor_templates)
    two_card_combos = [v for v in included_variants if v.card_count + (not v.complete) <= 2]
    early_game_two_card_combos = [v for v in two_card_combos if v.mana_value <= 4]
    reasons = []
    bracket = 1
    if not total_mass_land_denial_count and not total_extra_turn_count and not two_card_combos and not game_changers and total_tutor_count <= 1:
        bracket = 2
        reasons.extend([
            'it has no game changers',
            'no mass land denial',
            'no chained extra turns',
            'at most 1 tutor',
        ])
        if single and len(included_variants) == 1:
            reasons.append('it requires more than two cards' if included_variants[0].card_count > 2 else 'it would require at least another card to be complete and impactful')
        elif single:
            reasons.append('it is not a two-card combo')
        elif included_variants:
            reasons.append('no two-card combos')
        else:
            reasons.append('no combos')
    elif not total_mass_land_denial_count and not total_extra_turn_count and not early_game_two_card_combos and len(game_changers) <= 3:
        bracket = 3
        reasons.extend([
            'it has no mass land denial',
            'no extra turns',
        ])
        if total_tutor_count > 1:
            reasons.append('more than 1 tutor')
        if game_changers:
            reasons.append(f'only {len(game_changers)} game changer{"s" if len(game_changers) > 1 else ""}')
        if single:
            reasons.append('it is not an early game two-card combo')
        elif included_variants:
            reasons.append('no early game two-card combos (costing at most 4 mana upfront is considered early game)')
        else:
            reasons.append('no combos')
    else:
        if total_mass_land_denial_count:
            reasons.append('it contains mass land denial')
        if total_extra_turn_count:
            reasons.append('it contains chained extra turns')
        if len(game_changers) > 3:
            reasons.append(f'it contains {len(game_changers)} game changers')
        if not early_game_two_card_combos:
            bracket = 4
            if single:
                reasons.append('it is not an early game two-card combo')
            elif included_variants:
                reasons.append('no early game two-card combos (costing at most 4 mana upfront is considered early game)')
        else:
            bracket = 5
            reasons.extend([
                'it doesn\'t comply with bracket 3 guidelines',
            ])
            if single:
                reasons.append(f'it is is an early game two-card combo, only requiring {early_game_two_card_combos[0].mana_value} mana upfront')
            elif included_variants:
                reasons.append(f'it has {len(early_game_two_card_combos)} early game two-card combos (costing at most {max(v.mana_value for v in early_game_two_card_combos)} mana upfront)')
    if single:
        explanation = f'This combo could be included in bracket {bracket} decks because {chain_strings(reasons)}.'
    else:
        explanation = f'This decklist could be probably considered a bracket {bracket} deck because {chain_strings(reasons)}.'
    return BracketEstimate(
        bracket=bracket,
        explanation=explanation,
        game_changers=game_changers,
        mass_land_denial=mass_land_denial,
        mass_land_denial_templates=mass_land_denial_templates,
        extra_turn=extra_turn,
        extra_turn_templates=extra_turn_templates,
        tutor=tutor,
        tutor_templates=tutor_templates,
        two_card_combos=two_card_combos,
        early_game_two_card_combos=early_game_two_card_combos,
    )
