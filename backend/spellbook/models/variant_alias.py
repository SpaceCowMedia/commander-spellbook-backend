from django.db import models
from django.core.exceptions import ValidationError
from .variant import Variant
from .utils import recipe


def no_variant_with_this_id(value: str) -> None:
    if Variant.objects.filter(id=value).exists():
        raise ValidationError(f'Variant with id {value} exists. An alias cannot have the same id as a variant.')


class VariantAlias(models.Model):
    id = models.CharField(max_length=Variant._meta.get_field('id').max_length, primary_key=True, validators=[no_variant_with_this_id], help_text='Unique id of this variant alias', verbose_name='ID')
    variant = models.ForeignKey(to=Variant, on_delete=models.SET_NULL, null=True, blank=True, related_name='aliases', verbose_name='redirects to', help_text='Variant this alias redirects to')
    description = models.TextField(blank=True, help_text='Description of this variant alias')
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        verbose_name = 'variant alias'
        verbose_name_plural = 'variant aliases'
        default_manager_name = 'objects'

    def __str__(self):
        if self.variant:
            return f'Variant alias: {recipe([self.id], [self.variant.id])}'
        return f'Variant alias (dangling): {self.id}'
