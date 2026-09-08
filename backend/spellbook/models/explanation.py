from functools import cache
from django.db import models
from django.db.models import Index
from django.core.exceptions import ValidationError
from .constants import MAX_MANA_NEEDED_LENGTH
from .utils import case_insensitive_trigram_indexes
from .validators import MANA_VALIDATOR, TEXT_VALIDATORS


class Explanation(models.Model):
    '''What a combo, a variant, or a feature of a card says about itself: what it costs, what has to
    already be true, and how it goes. A variant assembles its own out of the ones written by every
    source it takes its texts from.'''

    mana_needed = models.CharField(blank=True, max_length=MAX_MANA_NEEDED_LENGTH, help_text='Mana needed. Use the {1}{W}{U}{B}{R}{G}{B/P}... format.', validators=[MANA_VALIDATOR, *TEXT_VALIDATORS])
    is_mana_needed_an_accurate_minimum = models.BooleanField(default=True, help_text='Does the first mana cost in this field represent the MINIMUM needed to start, ignoring all other text?')
    easy_prerequisites = models.TextField(blank=True, help_text='Easily achievable prerequisites.', validators=TEXT_VALIDATORS)
    notable_prerequisites = models.TextField(blank=True, help_text='Notable prerequisites.', validators=TEXT_VALIDATORS)
    description = models.TextField(blank=True, help_text='Long description, in steps. Here and in every other text field you can reference feature replacements with the [[name]] syntax. Optionally, you can also give it an alias to use later with [[name|alias]] and/or select one of the multiple copies with [[name$number]], where the number is the position of the needed feature row among the ones this combo needs for that feature, or with [[name$attribute]], where the attribute is the name of one of the attributes the feature was produced with. Uncheck "in replacements" on an ingredient to keep it out of the replacements of the features this combo produces. With the {{name}} syntax, and the same selectors, you can instead write here the text of this same field, taken from every combo or card producing that feature: those texts are then not appended to this one, because they have already been written where you mentioned them.', validators=TEXT_VALIDATORS)
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
