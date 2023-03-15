from rest_framework import serializers
from .models import Card, Template, Feature, Combo, Variant, CardInCombo, TemplateInCombo, CardInVariant, TemplateInVariant, IngredientInCombination


class ChoiceField(serializers.ChoiceField):
    def to_representation(self, obj):
        if obj == '' and self.allow_blank:
            return obj
        return self._choices[obj]

    def to_internal_value(self, data):
        # To support inserts with the value
        if data == '' and self.allow_blank:
            return ''

        for key, val in self._choices.items():
            if val == data:
                return key
        self.fail('invalid_choice', input=data)


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'legal', 'spoiler']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description']


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'legal', 'spoiler', 'features']


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = ['id', 'name', 'scryfall_query', 'scryfall_api']


class CardInComboSerializer(serializers.ModelSerializer):
    card = CardSerializer(many=False, read_only=True)
    zone_location = ChoiceField(choices=IngredientInCombination.ZoneLocation.choices)

    class Meta:
        model = CardInCombo
        fields = ['card', 'zone_location', 'card_state']


class TemplateInComboSerializer(serializers.ModelSerializer):
    template = TemplateSerializer(many=False, read_only=True)
    zone_location = ChoiceField(choices=IngredientInCombination.ZoneLocation.choices)

    class Meta:
        model = TemplateInCombo
        fields = ['template', 'zone_location', 'card_state']


class ComboDetailSerializer(serializers.ModelSerializer):
    produces = FeatureSerializer(many=True, read_only=True)
    needs = FeatureSerializer(many=True, read_only=True)
    uses = CardInComboSerializer(source='cardincombo_set', many=True, read_only=True)
    requires = TemplateInComboSerializer(source='templateincombo_set', many=True, read_only=True)

    class Meta:
        model = Combo
        fields = [
            'id',
            'produces',
            'needs',
            'uses',
            'requires',
            'mana_needed',
            'other_prerequisites',
            'description']


class ComboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combo
        fields = ['id']


class CardInVariantSerializer(serializers.ModelSerializer):
    card = CardSerializer(many=False, read_only=True)
    zone_location = ChoiceField(choices=IngredientInCombination.ZoneLocation.choices)

    class Meta:
        model = CardInVariant
        fields = ['card', 'zone_location', 'card_state']


class TemplateInVariantSerializer(serializers.ModelSerializer):
    template = TemplateSerializer(many=False, read_only=True)
    zone_location = ChoiceField(choices=IngredientInCombination.ZoneLocation.choices)

    class Meta:
        model = TemplateInVariant
        fields = ['template', 'zone_location', 'card_state']


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)

    class Meta:
        model = Variant
        fields = [
            'id',
            'uses',
            'requires',
            'produces',
            'of',
            'includes',
            'identity',
            'mana_needed',
            'other_prerequisites',
            'description']
