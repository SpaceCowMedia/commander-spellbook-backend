from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import Combo, CardInCombo, TemplateInCombo
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

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Combo]):
        return queryset.prefetch_related(
            'cardincombo_set__card',
            'templateincombo_set__template',
            'cardincombo_set',
            'templateincombo_set',
            'produces',
            'needs')
