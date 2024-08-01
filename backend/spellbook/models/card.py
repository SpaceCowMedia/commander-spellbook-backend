from django.db import models, connection
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.db.models.functions import Upper
from django.contrib.postgres.indexes import GinIndex, OpClass
from .constants import MAX_CARD_NAME_LENGTH
from .validators import TEXT_VALIDATORS
from .playable import Playable
from .utils import strip_accents, simplify_card_name_on_database, simplify_card_name_with_spaces_on_database
from .mixins import ScryfallLinkMixin, PreSaveModelMixin
from .feature import Feature
from .fields import KeywordsField
from .ingredient import Ingredient
from .feature_attribute import WithFeatureAttributes


class Card(Playable, PreSaveModelMixin, ScryfallLinkMixin):
    id: int
    oracle_id = models.UUIDField(unique=True, blank=True, null=True, verbose_name='Scryfall Oracle ID of card')
    name = models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, verbose_name='name of card')
    name_unaccented = models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, verbose_name='name of card without accents', editable=False)
    name_unaccented_simplified = models.GeneratedField(
        db_persist=True,
        expression=simplify_card_name_on_database('name_unaccented'),
        output_field=models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, verbose_name='name of card without accents or hyphens', editable=False))
    name_unaccented_simplified_with_spaces = models.GeneratedField(
        db_persist=True,
        expression=simplify_card_name_with_spaces_on_database('name_unaccented'),
        output_field=models.CharField(max_length=MAX_CARD_NAME_LENGTH, unique=True, blank=False, verbose_name='name of card without accents or hyphens, with spaces', editable=False))

    @classmethod
    def scryfall_fields(cls):
        return [
            'identity',
            'spoiler',
            'type_line',
            'oracle_text',
            'keywords',
            'mana_value',
            'reserved',
            'latest_printing_set',
            'reprinted',
        ]
    type_line = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, verbose_name='type line of card')
    oracle_text = models.TextField(blank=True, verbose_name='oracle text of card')
    keywords = KeywordsField(verbose_name='oracle keywords of card')
    mana_value = models.PositiveSmallIntegerField(default=0, verbose_name='mana value of card')
    reserved = models.BooleanField(default=False, help_text='Whether this card is part of the Reserved List', verbose_name='reserved list card')
    latest_printing_set = models.CharField(max_length=10, blank=True, help_text='Set code of latest printing of card', verbose_name='latest printing set of card')
    reprinted = models.BooleanField(default=False, help_text='Whether this card has been reprinted', verbose_name='reprinted card')

    features = models.ManyToManyField(
        to=Feature,
        related_name='cards',
        help_text='Features provided by this single card effects or characteristics',
        blank=True,
        verbose_name='features of card',
        through='FeatureOfCard')
    featureofcard_set: models.Manager['FeatureOfCard']
    added = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = 'card'
        verbose_name_plural = 'cards'
        default_manager_name = 'objects'
        ordering = ['name']
        indexes = [
            GinIndex(OpClass(Upper('name'), name='gin_trgm_ops'), name='card_name_trgm_idx'),
            GinIndex(OpClass(Upper('name_unaccented'), name='gin_trgm_ops'), name='card_name_unacc_trgm_idx'),
            GinIndex(OpClass(Upper('name_unaccented_simplified'), name='gin_trgm_ops'), name='card_name_unac_sim_trgm_idx'),
            GinIndex(OpClass(Upper('name_unaccented_simplified_with_spaces'), name='gin_trgm_ops'), name='card_name_unac_sim_sp_trgm_idx'),
            GinIndex(OpClass(Upper('type_line'), name='gin_trgm_ops'), name='card_type_line_trgm_idx'),
            GinIndex(OpClass(Upper('oracle_text'), name='gin_trgm_ops'), name='card_oracle_text_trgm_idx'),
            GinIndex(fields=['keywords'], name='card_keywords_trgm_idx'),
        ] if connection.vendor == 'postgresql' else []

    def __str__(self):
        return self.name

    def cards(self):
        return [self.name] if self.name else []

    def pre_save(self):
        self.name_unaccented = strip_accents(self.name)

    def is_legendary(self) -> bool:
        return 'Legendary' in self.type_line

    def is_creature(self) -> bool:
        return 'Creature' in self.type_line

    def is_instant(self) -> bool:
        return 'Instant' in self.type_line

    def is_sorcery(self) -> bool:
        return 'Sorcery' in self.type_line


@receiver(post_save, sender=Card, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance, created, raw, **kwargs):
    if raw or created:
        return
    from .variant import Variant
    variants = Variant.recipes_prefetched.filter(uses=instance)
    variants_to_save = []
    for variant in variants:
        requires_commander = any(civ.must_be_commander for civ in variant.cardinvariant_set.all()) \
            or any(tiv.must_be_commander for tiv in variant.templateinvariant_set.all())
        if variant.update(variant.uses.all(), requires_commander):
            variants_to_save.append(variant)
        new_variant_name = variant._str()
        if new_variant_name != variant.name:
            variant.name = new_variant_name
            variants_to_save.append(variant)
    Variant.objects.bulk_update(variants_to_save, fields=Variant.playable_fields() + ['name'])


@receiver(post_save, sender=Card, dispatch_uid='update_combo_fields')
def update_combo_fields(sender, instance, created, raw, **kwargs):
    if raw or created:
        return
    from .combo import Combo
    combos = Combo.recipes_prefetched.filter(uses=instance)
    combos_to_save = []
    for combo in combos:
        new_combo_name = combo._str()
        if new_combo_name != combo.name:
            combo.name = new_combo_name
            combos_to_save.append(combo)
    Combo.objects.bulk_update(combos_to_save, fields=['name'])


class FeatureOfCard(Ingredient, WithFeatureAttributes):
    id: int
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int
    other_prerequisites = models.TextField(blank=True, help_text='Other prerequisites that enable the feature for this card.', validators=TEXT_VALIDATORS)

    def __str__(self):
        return f'{self.feature} for card {self.card.pk}'

    class Meta(Ingredient.Meta):
        unique_together = [('feature', 'card')]
