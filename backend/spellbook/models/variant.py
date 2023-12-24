from typing import Iterable
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from sortedm2m.fields import SortedManyToManyField
from .playable import Playable
from .mixins import ScryfallLinkMixin, PreSaveModelMixin
from .card import Card
from .template import Template
from .feature import Feature
from .ingredient import IngredientInCombination
from .combo import Combo
from .job import Job
from .validators import TEXT_VALIDATORS, MANA_VALIDATOR
from .utils import recipe, mana_value, merge_identities


class Variant(Playable, PreSaveModelMixin, ScryfallLinkMixin):
    class Status(models.TextChoices):
        NEW = 'N'
        DRAFT = 'D'
        OK = 'OK'
        EXAMPLE = 'E'
        RESTORE = 'R'
        NOT_WORKING = 'NW'

    @classmethod
    def public_statuses(cls):
        return (cls.Status.OK, cls.Status.EXAMPLE)

    id = models.CharField(max_length=128, primary_key=True, unique=True, blank=False, help_text='Unique ID for this variant', editable=False)
    uses = models.ManyToManyField(
        to=Card,
        related_name='used_in_variants',
        help_text='Cards that this variant uses',
        editable=False,
        through='CardInVariant')
    requires = models.ManyToManyField(
        to=Template,
        related_name='required_by_variants',
        help_text='Templates that this variant requires',
        blank=True,
        verbose_name='required templates',
        through='TemplateInVariant')
    produces = SortedManyToManyField(
        to=Feature,
        related_name='produced_by_variants',
        help_text='Features that this variant produces',
        editable=False)
    includes = models.ManyToManyField(
        to=Combo,
        related_name='included_in_variants',
        help_text='Combo that this variant includes',
        editable=False)
    of = models.ManyToManyField(
        to=Combo,
        related_name='variants',
        help_text='Combo that this variant is an instance of',
        editable=False)
    status = models.CharField(choices=Status.choices, db_default=Status.NEW, help_text='Variant status for editors', max_length=2)
    mana_needed = models.CharField(blank=True, max_length=200, help_text='Mana needed for this combo. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR])
    mana_value_needed = models.PositiveIntegerField(editable=False, help_text='Mana value needed for this combo. Calculated from mana_needed.')
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites for this variant.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    generated_by = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='Job that generated this variant', related_name='variants')
    popularity = models.PositiveIntegerField(db_default=0, editable=False, help_text='Popularity of this variant, provided by EDHREC')

    class Meta:
        ordering = ['-status', '-created']
        verbose_name = 'variant'
        verbose_name_plural = 'variants'
        indexes = [
            models.Index(fields=['-popularity']),
            models.Index(fields=['-created']),
            models.Index(fields=['-updated']),
        ]

    def cards(self):
        return self.uses.order_by('cardinvariant')

    def templates(self):
        return self.requires.order_by('templateinvariant')

    def __str__(self):
        if self.pk is None:
            return f'New variant with unique id <{self.id}>'
        produces = list(self.produces.all()[:4])
        return recipe([str(card) for card in self.cards()] + [str(template) for template in self.templates()], [str(feature) for feature in produces])

    def pre_save(self):
        self.mana_value_needed = mana_value(self.mana_needed)

    def update(self, cards: Iterable['Card'], requires_commander: bool) -> bool:
        '''Returns True if any field was changed, False otherwise.'''
        cards = list(cards)
        old_values = {field: getattr(self, field) for field in self.playable_fields()}
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
        self.legal_modern = not requires_commander and all(playable.legal_modern for playable in cards)
        self.legal_pioneer = not requires_commander and all(playable.legal_pioneer for playable in cards)
        self.legal_standard = not requires_commander and all(playable.legal_standard for playable in cards)
        self.legal_pauper = not requires_commander and all(playable.legal_pauper for playable in cards)
        self.price_tcgplayer = sum(playable.price_tcgplayer for playable in cards)
        self.price_cardkingdom = sum(playable.price_cardkingdom for playable in cards)
        self.price_cardmarket = sum(playable.price_cardmarket for playable in cards)
        new_values = {field: getattr(self, field) for field in self.playable_fields()}
        return old_values != new_values


class CardInVariant(IngredientInCombination):
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.card} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('card', 'variant')]


class TemplateInVariant(IngredientInCombination):
    template = models.ForeignKey(to=Template, on_delete=models.CASCADE)
    variant = models.ForeignKey(to=Variant, on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.template} in {self.variant.pk}'

    class Meta(IngredientInCombination.Meta):
        unique_together = [('template', 'variant')]


@receiver(post_save, sender=Variant.uses.through, dispatch_uid='update_variant_on_cards')
@receiver(post_save, sender=Variant.requires.through, dispatch_uid='update_variant_on_templates')
def update_variant_on_ingredient(sender, instance, **kwargs):
    variant = instance.variant
    requires_commander = any(civ.must_be_commander for civ in variant.cardinvariant_set.all()) \
        or any(tiv.must_be_commander for tiv in variant.templateinvariant_set.all())
    if variant.update(variant.uses.all(), requires_commander):
        variant.save()
