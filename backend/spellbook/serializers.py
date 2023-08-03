from rest_framework import serializers
from spellbook.models import Card, Template, Feature, IngredientInCombination, Combo, CardInCombo, TemplateInCombo, Variant, CardInVariant, TemplateInVariant


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'legal', 'spoiler']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description', 'utility']


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
    zone_locations = serializers.SerializerMethodField()

    def get_zone_locations(self, obj):
        return list(obj.zone_locations)

    class Meta:
        model = CardInCombo
        fields = [
            'card',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class TemplateInComboSerializer(serializers.ModelSerializer):
    template = TemplateSerializer(many=False, read_only=True)
    zone_locations = serializers.SerializerMethodField()

    def get_zone_locations(self, obj):
        return list(obj.zone_locations)

    class Meta:
        model = TemplateInCombo
        fields = [
            'template',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class ComboDetailSerializer(serializers.ModelSerializer):
    produces = FeatureSerializer(many=True, read_only=True)
    needs = FeatureSerializer(many=True, read_only=True)
    uses = CardInComboSerializer(source='cardincombo_set', many=True, read_only=True)
    requires = TemplateInComboSerializer(source='templateincombo_set', many=True, read_only=True)

    class Meta:
        model = Combo
        fields = [
            'id',
            'kind',
            'produces',
            'needs',
            'uses',
            'requires',
            'mana_needed',
            'other_prerequisites',
            'description',
        ]


class ComboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combo
        fields = ['id']


class IngredientInVariantSerializer(serializers.ModelSerializer):
    zone_locations = serializers.SerializerMethodField()
    battlefield_card_state = serializers.SerializerMethodField()
    exile_card_state = serializers.SerializerMethodField()
    library_card_state = serializers.SerializerMethodField()
    graveyard_card_state = serializers.SerializerMethodField()
    must_be_commander = serializers.SerializerMethodField()

    def get_zone_locations(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return list(obj.zone_locations)

    def get_battlefield_card_state(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return obj.battlefield_card_state

    def get_exile_card_state(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return obj.exile_card_state

    def get_library_card_state(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return obj.library_card_state

    def get_graveyard_card_state(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return obj.graveyard_card_state

    def get_must_be_commander(self, obj):
        if obj.variant.status != Variant.Status.OK:
            return None
        return obj.must_be_commander


class CardInVariantSerializer(IngredientInVariantSerializer):
    card = CardSerializer(many=False, read_only=True)

    class Meta:
        model = CardInVariant
        fields = [
            'card',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class TemplateInVariantSerializer(IngredientInVariantSerializer):
    template = TemplateSerializer(many=False, read_only=True)

    class Meta:
        model = TemplateInVariant
        fields = [
            'template',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)
    mana_needed = serializers.SerializerMethodField()
    other_prerequisites = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_mana_needed(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.mana_needed

    def get_other_prerequisites(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.other_prerequisites

    def get_description(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.description

    class Meta:
        model = Variant
        fields = [
            'id',
            'status',
            'uses',
            'requires',
            'produces',
            'of',
            'includes',
            'identity',
            'mana_needed',
            'other_prerequisites',
            'description',
            'legal',
            'spoiler',
        ]
