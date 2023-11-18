from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Variant, CardInVariant, TemplateInVariant
from .combo_serializer import ComboSerializer
from .feature_serializer import FeatureSerializer
from .card_serializer import CardSerializer
from .template_serializer import TemplateSerializer
from .legalities_serializer import LegalitiesSerializer
from .prices_serializer import PricesSerializer


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


class VariantLegalitiesSerializer(LegalitiesSerializer):
    class Meta(LegalitiesSerializer.Meta):
        model = Variant


class VariantPricesSerializer(PricesSerializer):
    class Meta(PricesSerializer.Meta):
        model = Variant


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)
    mana_needed = serializers.SerializerMethodField()
    mana_value_needed = serializers.SerializerMethodField()
    other_prerequisites = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    legalities = VariantLegalitiesSerializer(source='*', read_only=True)
    prices = VariantPricesSerializer(source='*', read_only=True)

    def get_mana_needed(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.mana_needed

    def get_mana_value_needed(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.mana_value_needed

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
            'mana_value_needed',
            'other_prerequisites',
            'description',
            'spoiler',
            'legalities',
            'prices',
        ]

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Variant]):
        return queryset.prefetch_related(
            'cardinvariant_set__card',
            'templateinvariant_set__template',
            'cardinvariant_set',
            'templateinvariant_set',
            'produces',
            'of',
            'includes')
