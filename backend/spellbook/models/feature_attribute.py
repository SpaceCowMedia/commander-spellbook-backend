from django.db import models
from django.dispatch import receiver
from django.db.models.signals import post_save
from .feature import Feature
from .constants import MAX_FEATURE_NAME_LENGTH
from .mixins import NamedModel
from .validators import NO_RESERVED_CHARACTERS_VALIDATOR


class FeatureAttribute(NamedModel):
    id: int
    name = NamedModel.name_field(max_length=MAX_FEATURE_NAME_LENGTH, help_text='Name of the attribute, usable to select a feature replacement with the [[feature$attribute]] syntax', validators=[NO_RESERVED_CHARACTERS_VALIDATOR])
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
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='used_as_attribute_in_%(class)s')

    class Meta:
        abstract = True


class WithFeatureAttributesMatcher(models.Model):
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)
    feature_id: int
    any_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_any_of_in_%(class)s')
    all_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_all_of_in_%(class)s')
    none_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_none_of_in_%(class)s')

    class Meta:
        abstract = True
