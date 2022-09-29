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
    uses = CardSerializer(many=True, read_only=True)

    class Meta:
        model = Combo
        fields = [
            'id',
            'produces',
            'needs',
            'uses',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites',
            'description']


class VariantSerializer(serializers.ModelSerializer):
    uses = CardSerializer(many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)

    class Meta:
        model = Variant
        fields = [
            'id',
            'unique_id',
            'uses',
            'produces',
            'of',
            'includes',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites',
            'description']
