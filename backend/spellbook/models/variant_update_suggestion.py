from django.db import models
from django.contrib.auth.models import User
from . import Variant
from .validators import TEXT_VALIDATORS


class VariantUpdateSuggestion(models.Model):
    class Status(models.TextChoices):
        NEW = 'N'
        AWAITING_DISCUSSION = 'AD'
        PENDING_APPROVAL = 'PA'
        ACCEPTED = 'A'
        REJECTED = 'R'

    id: int
    status = models.CharField(choices=Status.choices, default=Status.NEW, help_text='Suggestion status for editors', max_length=2)
    notes = models.TextField(blank=True, help_text='Notes written by editors', validators=TEXT_VALIDATORS)
    comment = models.TextField(blank=True, max_length=2**10, help_text='Comment written by the user that suggested this update', validators=TEXT_VALIDATORS)
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    suggested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, help_text='User that suggested this update', related_name='variant_update_suggestions')
    issue = models.TextField(blank=False, help_text='Description of the problem', validators=TEXT_VALIDATORS)
    solution = models.TextField(blank=True, help_text='Description of the solution', validators=TEXT_VALIDATORS)
    variants: models.Manager['VariantInVariantUpdateSuggestion']

    class Meta:
        verbose_name = 'variant update suggestion'
        verbose_name_plural = 'variant update suggestions'
        default_manager_name = 'objects'
        ordering = [
            models.Case(
                *(models.When(status=s, then=models.Value(i)) for i, s in enumerate(('N', 'PA', 'AD', 'A', 'R'))),
                default=models.Value(10),
            ),
            'created',
        ]

    def __str__(self) -> str:
        issue = self.issue or ''
        issue_message = issue[:40] + ('...' if len(issue) > 40 else '')
        if self.id is None:
            return f'New Update Suggestion: "{issue_message}"'
        return f'Update Suggestion #{self.id}: {issue_message}'


class VariantInVariantUpdateSuggestion(models.Model):
    variant = models.ForeignKey(Variant, on_delete=models.CASCADE, help_text='Variant used in this suggestion', related_name='variant_update_suggestions')
    variant_id: str
    suggestion = models.ForeignKey(VariantUpdateSuggestion, on_delete=models.CASCADE, related_name='variants', help_text='Variant update suggestion this variant is used in')
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
