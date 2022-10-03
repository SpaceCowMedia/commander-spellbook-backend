from rest_framework import serializers
from .models import Card, Template, Feature, Combo, Variant


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description']


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'features']


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = ['id', 'name', 'scryfall_query', 'scryfall_api']


class ComboSerializer(serializers.ModelSerializer):
    produces = FeatureSerializer(many=True, read_only=True)
    needs = FeatureSerializer(many=True, read_only=True)
    uses = CardSerializer(many=True, read_only=True)
    requires = TemplateSerializer(many=True, read_only=True)

    class Meta:
        model = Combo
        fields = [
            'id',
            'produces',
            'needs',
            'uses',
            'requires',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites',
            'description']


class VariantSerializer(serializers.ModelSerializer):
    uses = CardSerializer(many=True, read_only=True)
    requires = TemplateSerializer(many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)

    class Meta:
        model = Variant
        fields = [
            'id',
            'unique_id',
            'uses',
            'requires',
            'produces',
            'of',
            'includes',
            'identity',
            'zone_locations',
            'cards_state',
            'mana_needed',
            'other_prerequisites',
            'description']
