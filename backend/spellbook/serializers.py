from rest_framework import serializers
from .models import Card, Feature, Combo, Variant


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['name', 'oracle_id', 'features']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['name', 'description']


class ComboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combo
        fields = ['produces', 'needs', 'includes', 'prerequisites', 'description']


class VariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variant
        fields = ['includes', 'produces', 'of', 'status', 'prerequisites', 'description']
