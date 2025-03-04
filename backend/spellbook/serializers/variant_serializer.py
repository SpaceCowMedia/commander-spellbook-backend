from django.db.models import QuerySet
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from spellbook.models import Variant, CardInVariant, TemplateInVariant, FeatureProducedByVariant
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
    must_be_commander = serializers.BooleanField(read_only=True)

    @extend_schema_field(serializers.ListSerializer(child=serializers.CharField()))
    def get_zone_locations(self, obj):
        return list(obj.zone_locations)

    @extend_schema_field(serializers.CharField(required=False))
    def get_battlefield_card_state(self, obj):
        if obj.variant.status == Variant.Status.EXAMPLE:
            return None
        return obj.battlefield_card_state

    @extend_schema_field(serializers.CharField(required=False))
    def get_exile_card_state(self, obj):
        if obj.variant.status == Variant.Status.EXAMPLE:
            return None
        return obj.exile_card_state

    @extend_schema_field(serializers.CharField(required=False))
    def get_library_card_state(self, obj):
        if obj.variant.status == Variant.Status.EXAMPLE:
            return None
        return obj.library_card_state

    @extend_schema_field(serializers.CharField(required=False))
    def get_graveyard_card_state(self, obj):
        if obj.variant.status == Variant.Status.EXAMPLE:
            return None
        return obj.graveyard_card_state


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
            'quantity',
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
            'quantity',
        ]


class FeatureProducedByVariantSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(many=False, read_only=True)

    class Meta:
        model = FeatureProducedByVariant
        fields = [
            'feature',
            'quantity',
        ]


class VariantLegalitiesSerializer(LegalitiesSerializer):
    class Meta(LegalitiesSerializer.Meta):
        model = Variant


class VariantPricesSerializer(PricesSerializer):
    class Meta(PricesSerializer.Meta):
        model = Variant


class BracketTagSerializer(serializers.ChoiceField):
    def __init__(self, **kwargs):
        super().__init__(Variant.BracketTag.choices, read_only=True, source='bracket_tag_override', **kwargs)

    def get_attribute(self, instance):
        value = super().get_attribute(instance)
        if value is None:
            self.source = None
            self.bind('bracket_tag', self.parent)
            return super().get_attribute(instance)
        return value


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureProducedByVariantSerializer(source='featureproducedbyvariant_set', many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)
    mana_needed = serializers.SerializerMethodField()
    mana_value_needed = serializers.SerializerMethodField()
    easy_prerequisites = serializers.SerializerMethodField()
    notable_prerequisites = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    popularity = serializers.IntegerField(read_only=True, min_value=0, allow_null=True)
    legalities = VariantLegalitiesSerializer(source='*', read_only=True)
    prices = VariantPricesSerializer(source='*', read_only=True)
    bracket_tag = BracketTagSerializer()

    @extend_schema_field(serializers.CharField(required=False))
    def get_mana_needed(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.mana_needed

    @extend_schema_field(serializers.IntegerField(required=False, min_value=0))
    def get_mana_value_needed(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.mana_value_needed

    @extend_schema_field(serializers.CharField(required=False))
    def get_notable_prerequisites(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.notable_prerequisites

    @extend_schema_field(serializers.CharField(required=False))
    def get_easy_prerequisites(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.easy_prerequisites

    @extend_schema_field(serializers.CharField(required=False))
    def get_description(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.description

    @extend_schema_field(serializers.CharField(required=False))
    def get_notes(self, obj: Variant):
        if obj.status == Variant.Status.EXAMPLE:
            return None
        return obj.public_notes

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
            'easy_prerequisites',
            'notable_prerequisites',
            'description',
            'notes',
            'popularity',
            'spoiler',
            'bracket_tag',
            'legalities',
            'prices',
            'variant_count',
        ]

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Variant]):
        return queryset.prefetch_related(
            'cardinvariant_set',
            'templateinvariant_set',
            'featureproducedbyvariant_set',
            'featureproducedbyvariant_set__feature',
            'cardinvariant_set__card',
            'templateinvariant_set__template',
            'of',
            'includes',
        )
