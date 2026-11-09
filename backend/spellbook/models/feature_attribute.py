from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from .feature import Feature
from .constants import MAX_ATTRIBUTE_VALUE_LENGTH, MAX_FEATURE_NAME_LENGTH
from .mixins import NamedModel
from .fields import DictionaryField
from .references import DEFAULT_KEY, TEXT_KEYS, format_feature_reference
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
    it provides under that attribute if any, and the dictionary of its built-in keys.'''
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    dictionary = DictionaryField(attribute_keys=False, help_text=(
        'What this provides for the feature, key by key, besides its attributes.'
        f' The built-in keys {DEFAULT_KEY}, {", ".join(TEXT_KEYS)} hold a text or a list of texts, which a combo needing the feature writes with the {format_feature_reference("feature", key="key")} syntax,'
        ' and override what is provided without them, the name of the card or what the combo brings, its own texts counting as lists of one:'
        ' a text replaces it, a list adds to it, and a blank text leaves it out.'
        f' The keys {", ".join(TEXT_KEYS)} are texts of the variants, written in the field of the same name wherever they write what the feature provides.'
        f' Every other key is one of the attributes this produces the feature with, holding nothing or a text written with the {format_feature_reference("feature", key="attribute")} syntax.'
    ))

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
