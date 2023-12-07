from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Feature


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Feature]):
        return queryset.all()
