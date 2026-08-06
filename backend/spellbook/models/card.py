from functools import cached_property
from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from .constants import MAX_CARD_NAME_LENGTH, MAX_MANA_NEEDED_LENGTH
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS
from .playable import Playable
from .utils import strip_accents, simplify_card_name_on_database, simplify_card_name_with_spaces_on_database, cast_case_insensitive_trigram_indexes, case_insensitive_trigram_indexes, CardType
from .recipe import update_variants, update_combo_names
from .mixins import ScryfallLinkMixin, PreSaveModelMixin, NamedModel
from .feature import Feature
from .fields import KeywordsField
from .ingredient import Ingredient
from .feature_attribute import WithFeatureAttributes


class LayoutRotation(models.TextChoices):
    CLOCKWISE = 'clockwise', 'Clockwise'
    COUNTERCLOCKWISE = 'counterclockwise', 'Counterclockwise'
    FLIP = 'flip', 'Flip'


class Card(NamedModel, Playable, PreSaveModelMixin, ScryfallLinkMixin):
    id: int
    oracle_id = models.UUIDField(unique=True, blank=True, null=True, verbose_name='Scryfall Oracle ID of card')
    name = NamedModel.name_field(max_length=MAX_CARD_NAME_LENGTH, verbose_name='name of card')
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
            'color',
            'spoiler',
            'faces',
            'type_line',
            'oracle_text',
            'keywords',
            'mana_value',
            'reserved',
            'latest_printing_set',
            'reprinted',
            'game_changer',
            'tutor',
            'mass_land_denial',
            'extra_turn',
            'image_uri_front_png',
            'image_uri_front_large',
            'image_uri_front_normal',
            'image_uri_front_small',
            'image_uri_front_art_crop',
            'layout_rotation_front',
            'image_uri_back_png',
            'image_uri_back_large',
            'image_uri_back_normal',
            'image_uri_back_small',
            'image_uri_back_art_crop',
        ]
    faces = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)], help_text='Number of faces (subcards) this card is split into, such as double-faced cards, adventures, split cards and so on. 1 for normal cards.', verbose_name='number of faces of card')
    type_line = models.CharField(max_length=MAX_CARD_NAME_LENGTH, blank=True, verbose_name='type line of card')
    oracle_text = models.TextField(blank=True, verbose_name='oracle text of card')
    keywords = KeywordsField(verbose_name='oracle keywords of card')
    reserved = models.BooleanField(default=False, help_text='Whether this card is part of the Reserved List', verbose_name='reserved list card')
    latest_printing_set = models.CharField(max_length=10, blank=True, help_text='Set code of latest printing of card', verbose_name='latest printing set of card')
    reprinted = models.BooleanField(default=False, help_text='Whether this card has been reprinted', verbose_name='reprinted card')
    tutor = models.BooleanField(default=False, help_text='Whether this card can tutor for other cards', verbose_name='tutor card')
    mass_land_denial = models.BooleanField(default=False, help_text='Whether this card can inhibit or destroy numerous lands', verbose_name='mass land denial card')
    extra_turn = models.BooleanField(default=False, help_text='Whether this card grants an extra turn', verbose_name='extra turn card')
    game_changer = models.BooleanField(default=False, help_text='Whether this card is in the official Game Changer card list', verbose_name='game changer card')
    image_uri_front_png = models.URLField(blank=True, null=True, verbose_name='image URI of the front of the card in PNG format')
    image_uri_front_large = models.URLField(blank=True, null=True, verbose_name='image URI of the front of the card in large format')
    image_uri_front_normal = models.URLField(blank=True, null=True, verbose_name='image URI of the front of the card in normal format')
    image_uri_front_small = models.URLField(blank=True, null=True, verbose_name='image URI of the front of the card in small format')
    image_uri_front_art_crop = models.URLField(blank=True, null=True, verbose_name='image URI of the card art crop')
    layout_rotation_front = models.CharField(max_length=20, choices=LayoutRotation.choices, blank=True, null=True, verbose_name='layout rotation of the front of the card')
    image_uri_back_png = models.URLField(blank=True, null=True, verbose_name='image URI of the back of the card in PNG format')
    image_uri_back_large = models.URLField(blank=True, null=True, verbose_name='image URI of the back of the card in large format')
    image_uri_back_normal = models.URLField(blank=True, null=True, verbose_name='image URI of the back of the card in normal format')
    image_uri_back_small = models.URLField(blank=True, null=True, verbose_name='image URI of the back of the card in small format')
    image_uri_back_art_crop = models.URLField(blank=True, null=True, verbose_name='image URI of the back of the card art crop')

    features: 'models.ManyToManyField[Feature, FeatureOfCard]' = models.ManyToManyField(
        to=Feature,
        through='FeatureOfCard',
        related_name='cards',
        help_text='Features provided by this single card effects or characteristics',
        blank=True,
        verbose_name='features of card',
    )
    featureofcard_set: models.Manager['FeatureOfCard']
    variant_count = models.PositiveIntegerField(default=0, editable=False)
    added = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = 'card'
        verbose_name_plural = 'cards'
        default_manager_name = 'objects'
        ordering = ['name']
        indexes = case_insensitive_trigram_indexes(
            'card',
            'name',
            'type_line',
            'oracle_text',
            name_unaccented='name_unacc',
            name_unaccented_simplified='name_unac_sim',
            name_unaccented_simplified_with_spaces='name_unac_sim_sp',
        ) + cast_case_insensitive_trigram_indexes('card', 'keywords')

    def __str__(self):
        return self.name

    def cards(self):
        return [self.name] if self.name else []

    def face_name(self, face: int | None, short: bool = False) -> str:
        '''Returns the name of the given 1-based face index, or the whole card name if the index is blank or out of range.
        With short, the name of a legendary creature is cut before the comma, the way such a card is commonly called.'''
        names = self.name.split(' // ')
        if face is not None and 1 <= face <= len(names):
            name = names[face - 1]
            face_types = self.card_types[face - 1] if face <= len(self.card_types) else []
        else:
            name = self.name
            face_types = self.card_types[0] if len(names) == 1 and self.card_types else []
        if short and ',' in name and set(face_types).issuperset({CardType.LEGENDARY, CardType.CREATURE}):
            return name.split(',', 1)[0]
        return name

    def pre_save(self):
        self.name_unaccented = strip_accents(self.name)

    @cached_property
    def card_types(self):
        return [face_type_line.replace('Time Lord', 'TimeLord').split() for face_type_line in self.type_line.split(' // ')]

    def is_of_type(self, card_type: CardType) -> bool:
        return card_type.value in self.type_line

    @cached_property
    def is_commander(self) -> bool:
        if self.name in (
                'Asmoranomardicadaistinaculdacar',
                'Grist, the Hunger Tide',
                'The Grand Calcutron',
                'The Eternity Elevator',
                'Enolc, Perfect Clone',
                'The Faction Dragon',
                'The Magical City, New',
                'The Waffle Restaurant',
                'The Mystery Raceway',
                'The Goblin Sparring Grounds',
        ):
            return True
        if not self.mana_value:
            return False
        if not self.legal_commander:
            return False
        for face_type_line in self.card_types:
            face_types = set(face_type_line)
            if face_types.issuperset({CardType.LEGENDARY, CardType.CREATURE}):
                return True
            if face_types.issuperset({CardType.LEGENDARY, 'Spacecraft'}):
                return True
            if face_types.issuperset({CardType.LEGENDARY, 'Vehicle'}):
                return True
            if 'Background' in face_types:
                return True
        if 'can be your commander' in self.oracle_text:
            return True
        return False


@receiver(post_save, sender=Card, dispatch_uid='update_variant_fields')
def update_variant_fields(sender, instance: Card, created, raw, **kwargs):
    # every field of a card takes part in the computed fields of its variants, the name included
    if raw or created:
        return
    update_variants(uses=instance)


@receiver(post_save, sender=Card, dispatch_uid='update_combo_fields')
def update_combo_fields(sender, instance: Card, created, raw, **kwargs):
    # the name of a combo is the only thing a card contributes to it
    if raw or created or not instance.renamed_from:
        return
    update_combo_names(uses=instance)


class WithUsedFace(models.Model):
    '''Mixin for models pointing to a Card, that allows to specify which face of a multi-faced card is used.'''
    card = models.ForeignKey(to=Card, on_delete=models.CASCADE)
    card_id: int

    used_face = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        default=None,
        validators=[MinValueValidator(1)],
        help_text='For multi-faced cards (double-faced, adventures, split cards...), the 1-based index of the face actually used. Leave blank to use the whole card.',
        verbose_name='used face',
    )

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.used_face is None:
            return
        try:
            card = self.card
        except ObjectDoesNotExist:
            return
        if card is None or card.faces <= 1:
            raise ValidationError({'used_face': 'A used face can only be specified for cards with more than one face.'})
        if self.used_face > card.faces:
            raise ValidationError({'used_face': f'The used face must be a number between 1 and {card.faces}.'})


class FeatureOfCard(Ingredient, WithFeatureAttributes, WithUsedFace):
    id: int
    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed for this card feature. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR, *TEXT_VALIDATORS])
    easy_prerequisites = models.TextField(blank=True, help_text='Easily achievable prerequisites for this card feature.', validators=TEXT_VALIDATORS)
    notable_prerequisites = models.TextField(blank=True, help_text='Notable prerequisites for this card feature.', validators=TEXT_VALIDATORS)

    @classmethod
    def text_fields_with_references(cls) -> list[str]:
        return [*super().text_fields_with_references(), 'mana_needed', 'easy_prerequisites', 'notable_prerequisites']

    class Meta(Ingredient.Meta):
        indexes = Ingredient.card_state_trigram_indexes('featureofcard') + case_insensitive_trigram_indexes(
            'featureofcard',
            'mana_needed',
            easy_prerequisites='easy_prereq',
            notable_prerequisites='notable_prereq',
        )

    def __str__(self):
        return f'{self.feature} for card {self.card_id}'
