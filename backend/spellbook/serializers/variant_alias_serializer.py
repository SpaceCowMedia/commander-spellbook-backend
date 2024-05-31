from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import VariantAlias


class VariantAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantAlias
        fields = ['id', 'variant']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[VariantAlias]):
        return queryset
