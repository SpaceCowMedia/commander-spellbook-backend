from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Card
from .feature_serializer import FeatureSerializer
from .legalities_serializer import LegalitiesSerializer
from .prices_serializer import PricesSerializer


class CardLegalitiesSerializer(LegalitiesSerializer):
    class Meta(LegalitiesSerializer.Meta):
        model = Card


class CardPricesSerializer(PricesSerializer):
    class Meta(PricesSerializer.Meta):
        model = Card


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)
    legalities = CardLegalitiesSerializer(source='*', read_only=True)
    prices = CardPricesSerializer(source='*', read_only=True)

    class Meta:
        model = Card
        fields = [
            'id',
            'name',
            'oracle_id',
            'identity',
            'type_line',
            'oracle_text',
            'spoiler',
            'features',
            'legalities',
            'prices',
        ]

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Card]):
        return queryset.prefetch_related('features')
