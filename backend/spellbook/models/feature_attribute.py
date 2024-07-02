from django.db import models
from .feature import Feature
from .constants import MAX_FEATURE_NAME_LENGTH


class FeatureAttribute(models.Model):
    id: int
    name = models.CharField(max_length=MAX_FEATURE_NAME_LENGTH, unique=True, blank=False)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WithFeatureAttributes(models.Model):
    attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='used_as_attribute_in_%(class)s')
    feature = models.ForeignKey(to=Feature, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class WithFeatureAttributesMatcher(models.Model):
    any_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_any_of_in_%(class)s')
    all_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_all_of_in_%(class)s')
    none_of_attributes = models.ManyToManyField(to=FeatureAttribute, blank=True, related_name='needed_as_none_of_in_%(class)s')

    class Meta:
        abstract = True
