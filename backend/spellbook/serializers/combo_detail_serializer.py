from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Combo, CardInCombo, TemplateInCombo, FeatureNeededInCombo, FeatureProducedInCombo, FeatureRemovedInCombo
from .feature_serializer import FeatureSerializer
from .card_serializer import CardSerializer
from .template_serializer import TemplateSerializer


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


class FeatureProducedInComboSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(many=False, read_only=True)

    class Meta:
        model = FeatureProducedInCombo
        fields = [
            'feature',
            'quantity',
        ]


class FeatureNeededInComboSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(many=False, read_only=True)

    class Meta:
        model = FeatureNeededInCombo
        fields = [
            'feature',
            'quantity',
        ]


class FeatureRemovedInComboSerializer(serializers.ModelSerializer):
    feature = FeatureSerializer(many=False, read_only=True)

    class Meta:
        model = FeatureRemovedInCombo
        fields = [
            'feature',
            'quantity',
        ]


class ComboDetailSerializer(serializers.ModelSerializer):
    produces = FeatureProducedInComboSerializer(source='featureproducedincombo_set', many=True, read_only=True)
    needs = FeatureNeededInComboSerializer(source='featureneededincombo_set', many=True, read_only=True)
    removes = FeatureRemovedInComboSerializer(source='featureremovedincombo_set', many=True, read_only=True)
    uses = CardInComboSerializer(source='cardincombo_set', many=True, read_only=True)
    requires = TemplateInComboSerializer(source='templateincombo_set', many=True, read_only=True)

    class Meta:
        model = Combo
        fields = [
            'id',
            'status',
            'produces',
            'removes',
            'needs',
            'uses',
            'requires',
            'mana_needed',
            'other_prerequisites',
            'description',
            'notes',
        ]

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Combo]):
        return queryset.prefetch_related(
            'cardincombo_set',
            'templateincombo_set',
            'featureproducedincombo_set',
            'featureremovedincombo_set',
            'featureneededincombo_set',
            'cardincombo_set__card',
            'templateincombo_set__template',
            'featureproducedincombo_set__feature',
            'featureremovedincombo_set__feature',
            'featureneededincombo_set__feature',
        )
