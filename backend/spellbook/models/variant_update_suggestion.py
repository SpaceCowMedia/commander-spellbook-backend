from django.db import models
from django.core.exceptions import ValidationError
from .suggestion import Suggestion
from . import Variant
from .validators import TEXT_VALIDATORS


class VariantUpdateSuggestion(Suggestion):
    class Kind(models.TextChoices):
        NOT_WORKING = 'NW'
        SPELLING_ERROR = 'SE'
        INCORRECT_INFO = 'II'
        WRONG_CARD = 'WC'
        VARIANT_GROUPING = 'VG'
        BRACKET_CLASSIFICATION = 'BC'
        OTHER = 'O'
    kind = models.CharField(choices=Kind.choices, max_length=2)
    issue = models.TextField(blank=False, validators=TEXT_VALIDATORS)
    solution = models.TextField(blank=True, validators=TEXT_VALIDATORS)
    variants: models.Manager['VariantInVariantUpdateSuggestion']

    class Meta(Suggestion.Meta):
        verbose_name = 'variant update suggestion'
        verbose_name_plural = 'variant update suggestions'

    def __str__(self) -> str:
        issue = self.issue or ''
        issue_message = issue[:40] + ('...' if len(issue) > 40 else '')
        if self.id is None:
            return f'New Update Suggestion: "{issue_message}"'
        return f'Update Suggestion #{self.id}: {issue_message}'

    @classmethod
    def validate(cls, variants: list[str]):
        if len(variants) != len(set(variants)):
            raise ValidationError('You cannot specify the same variant more than once.')


class VariantInVariantUpdateSuggestion(models.Model):
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, related_name='variant_update_suggestions')
    variant_id: str
    suggestion = models.ForeignKey(VariantUpdateSuggestion, on_delete=models.CASCADE, related_name='variants')
    suggestion_id: int
    issue = models.TextField(blank=True, help_text='Description of the issue specific for this variant', validators=TEXT_VALIDATORS)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['variant', 'suggestion'],
                name='unique_variant_in_update_suggestion',
                violation_error_message='This variant is already linked to this update suggestion.',
            )
        ]

    def spellbook_link(self, raw=False) -> str | None:
        if not self.variant_id:
            return ''
        return self.variant.spellbook_link(raw=raw)
