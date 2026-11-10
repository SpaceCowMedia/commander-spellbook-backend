from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from .feature import Feature
from .constants import MAX_ATTRIBUTE_VALUE_LENGTH, MAX_FEATURE_NAME_LENGTH
from .mixins import NamedModel
from .references import format_feature_reference
from .validators import ATTRIBUTE_NAME_VALIDATORS, TEXT_VALIDATORS


class FeatureAttribute(NamedModel):
    id: int
    name = NamedModel.name_field(max_length=MAX_FEATURE_NAME_LENGTH, help_text=f'Name of the attribute, which a producer can give a text, usable to select a feature replacement with the {format_feature_reference("feature", selector="attribute")} syntax, and to write the text a producer gives it with the {format_feature_reference("feature", key="attribute")} syntax', validators=ATTRIBUTE_NAME_VALIDATORS)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


@receiver(post_save, sender=FeatureAttribute, dispatch_uid='update_feature_attribute_references')
def update_feature_attribute_references(sender, instance: FeatureAttribute, created, raw, **kwargs):
    if raw or created or not instance.renamed_from:
        return
    from .references import replace_attribute_references
    replace_attribute_references(instance, instance.renamed_from)


class WithFeatureAttributes(models.Model):
    '''A producer of a feature, with the attributes it produces the feature with, each holding the text
    it provides under that attribute if any.'''
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int

    class Meta:
        abstract = True


class AttributeValue(models.Model):
    '''An attribute a producer produces its feature with, and the text it provides under that attribute,
    if any, which a combo needing the feature writes with the [[feature@attribute]] syntax.'''
    attribute = models.ForeignKey(to=FeatureAttribute, on_delete=models.CASCADE, db_column='featureattribute_id')
    attribute_id: int
    value = models.CharField(max_length=MAX_ATTRIBUTE_VALUE_LENGTH, blank=True, default='', validators=TEXT_VALIDATORS, help_text='What the producer provides under the attribute, written where a combo references it, if anything.')

    class Meta:
        abstract = True

    @classmethod
    def text_fields_with_references(cls) -> list[str]:
        return ['value']

    def __str__(self):
        return f'{self.attribute} of {self.producer}'  # type: ignore[attr-defined]


class WithFeatureAttributesMatcher(models.Model):
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    any_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_any_of_in_%(class)s')
    all_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_all_of_in_%(class)s')
    none_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_none_of_in_%(class)s')

    class Meta:
        abstract = True
