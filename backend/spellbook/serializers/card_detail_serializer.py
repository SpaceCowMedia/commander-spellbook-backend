from django.db.models import QuerySet
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from spellbook.models import Card, FeatureOfCard
from .feature_serializer import FeatureSerializer
from .legalities_serializer import LegalitiesSerializer
from .prices_serializer import PricesSerializer


class CardLegalitiesSerializer(LegalitiesSerializer):
    class Meta(LegalitiesSerializer.Meta):
        model = Card


class CardPricesSerializer(PricesSerializer):
    class Meta(PricesSerializer.Meta):
        model = Card


class FeatureOfCardSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(many=False, read_only=True)
    zone_locations = serializers.SerializerMethodField()

    @extend_schema_field(serializers.ListSerializer(child=serializers.CharField()))
    def get_zone_locations(self, obj):
        return list(obj.zone_locations)

    class Meta:
        model = FeatureOfCard
        fields = [
            'id',
            'feature',
            'quantity',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureOfCardSerializer(source='featureofcard_set', many=True, read_only=True)
    legalities = CardLegalitiesSerializer(source='*', read_only=True)
    prices = CardPricesSerializer(source='*', read_only=True)

    class Meta:
        model = Card
        fields = [
            'id',
            'name',
            'oracle_id',
            'identity',
            'variant_count',
            *Card.scryfall_fields(),
            'spoiler',
            'features',
            'legalities',
            'prices',
        ]

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Card]):
        return queryset.prefetch_related(
            'featureofcard_set',
            'featureofcard_set__feature',
        )
