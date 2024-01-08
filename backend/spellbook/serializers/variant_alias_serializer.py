from rest_framework import serializers
from spellbook.models import VariantAlias


class VariantAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = VariantAlias
        fields = ['id', 'variant', 'description']
