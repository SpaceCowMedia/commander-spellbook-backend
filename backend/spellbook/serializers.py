from rest_framework import serializers
from .models import Card, Feature, Combo, Variant


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description']


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'features']


class ComboSerializer(serializers.ModelSerializer):
    produces = FeatureSerializer(many=True, read_only=True)
    needs = FeatureSerializer(many=True, read_only=True)
    includes = CardSerializer(many=True, read_only=True)

    class Meta:
        model = Combo
        fields = ['id', 'produces', 'needs', 'includes', 'prerequisites', 'description']


class VariantSerializer(serializers.ModelSerializer):
    includes = CardSerializer(many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)

    class Meta:
        model = Variant
        fields = ['id', 'unique_id', 'includes', 'produces', 'of', 'prerequisites', 'description']
