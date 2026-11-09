from functools import cache
from django.db import models
from django.db.models import Index
from django.core.exceptions import ValidationError
from .constants import MAX_MANA_NEEDED_LENGTH
from .references import format_alias_reference, format_feature_reference, format_line_reference
from .utils import case_insensitive_trigram_indexes
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS


DESCRIPTION_HELP_TEXT = (
    'Long description, in steps.'
    f' Here and in every other text field you can reference the features this combo needs with the {format_feature_reference("name")} syntax, which writes the names of what produces them.'
    f' Add a key to write something else they provide: {format_feature_reference("name", key="description")} writes their descriptions, along with the ones of what they need in turn,'
    f' {format_feature_reference("name", key="mana_needed")} their mana needed, and any key in their dictionaries works the same way, while a key nothing provides writes nothing.'
    ' A text written in the field of its own name, as a description in this one, is then not appended to it again.'
    f' Optionally, you can select one of the multiple copies with {format_feature_reference("name", selector="number")},'
    ' where the number counts through the copies this combo needs of that feature, in the order of its needed feature rows,'
    f' or with {format_feature_reference("name", selector="attribute")}, where the attribute is the name of one of the attributes the feature was produced with.'
    ' The dictionary of an ingredient overrides what it brings to the features this combo produces and to its variants,'
    ' and the dictionary of a produced feature what this combo provides for it, its own texts counting as lists of one, in its variants too:'
    ' a text replaces, a list adds to a list, and a blank text leaves it out.'
    f' Give a reference an alias, as in {format_feature_reference("name", alias="alias")} or {format_feature_reference("name", selector="number", alias="alias")},'
    f' to repeat it anywhere in the same text as {format_alias_reference("alias")}, or with another key as {format_alias_reference("alias", key="key")}.'
    f' To mention a step, write {format_line_reference("X", "+")} for the line X lines below, {format_line_reference("Y", "-")} for the line Y lines above,'
    f' or {format_line_reference("Z")} for the Zth line of this text: each variant replaces it with the number that line ends up at.'
)


class Explanation(models.Model):
    '''What a combo or a variant says about itself: what it costs, what has to already be true, and how
    it goes. A variant assembles its own out of the texts of every combo it needs and the dictionaries
    of the rows and card features on the way.'''

    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR, *TEXT_VALIDATORS])
    is_mana_needed_an_accurate_minimum = models.BooleanField(default=True, help_text='Does the first mana cost in this field represent the MINIMUM needed to start, ignoring all other text?')
    easy_prerequisites = models.TextField(blank=True, help_text='Easily achievable prerequisites.', validators=TEXT_VALIDATORS)
    notable_prerequisites = models.TextField(blank=True, help_text='Notable prerequisites.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text=DESCRIPTION_HELP_TEXT, validators=TEXT_VALIDATORS)
    notes = models.TextField(blank=True, help_text='Notes that will be displayed on the site', validators=TEXT_VALIDATORS)
    comment = models.TextField(blank=True, help_text='Notes for the editors, not displayed on the site', validators=TEXT_VALIDATORS)

    @classmethod
    @cache
    def explanation_fields(cls) -> list[str]:
        return [
            'mana_needed',
            'is_mana_needed_an_accurate_minimum',
            'easy_prerequisites',
            'notable_prerequisites',
            'description',
            'notes',
            'comment',
        ]

    @classmethod
    def text_fields_with_references(cls) -> list[str]:
        return [field for field in cls.explanation_fields() if field != 'is_mana_needed_an_accurate_minimum']

    @classmethod
    def text_trigram_indexes(cls, prefix: str) -> list[Index]:
        return case_insensitive_trigram_indexes(
            prefix,
            'mana_needed',
            'description',
            'notes',
            'comment',
            easy_prerequisites='easy_prereq',
            notable_prerequisites='notable_prereq',
        )

    def clean(self):
        super().clean()
        if not self.mana_needed and not self.is_mana_needed_an_accurate_minimum:
            raise ValidationError(f'If {self._meta.get_field('mana_needed').verbose_name} is empty, {self._meta.get_field('is_mana_needed_an_accurate_minimum').verbose_name} must be True.')  # pyright: ignore[reportAttributeAccessIssue]

    class Meta:
        abstract = True
