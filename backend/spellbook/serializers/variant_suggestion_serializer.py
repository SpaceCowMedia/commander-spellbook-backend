from django.db import transaction
from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import CardUsedInVariantSuggestion, FeatureProducedInVariantSuggestion, TemplateRequiredInVariantSuggestion, VariantSuggestion, IngredientInCombination
from spellbook.models.utils import sanitize_apostrophes_and_quotes
from .user_serializer import UserSerializer
from .utils import StringMultipleChoiceField


class IngredientInVariantSuggestionSerializer(serializers.ModelSerializer):
    zone_locations = StringMultipleChoiceField(choices=IngredientInCombination.ZoneLocation.choices, allow_empty=False)

    def validate(self, attrs):
        IngredientInCombination.clean_data(attrs)
        return super().validate(attrs)


class CardUsedInVariantSuggestionSerializer(IngredientInVariantSuggestionSerializer):
    class Meta:
        model = CardUsedInVariantSuggestion
        fields = [
            'card',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class TemplateRequiredInVariantSuggestionSerializer(IngredientInVariantSuggestionSerializer):
    class Meta:
        model = TemplateRequiredInVariantSuggestion
        fields = [
            'template',
            'scryfall_query',
            'zone_locations',
            'battlefield_card_state',
            'exile_card_state',
            'library_card_state',
            'graveyard_card_state',
            'must_be_commander',
        ]


class FeatureProducedInVariantSuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureProducedInVariantSuggestion
        fields = [
            'feature',
        ]


class VariantSuggestionSerializer(serializers.ModelSerializer):
    uses = CardUsedInVariantSuggestionSerializer(many=True)
    requires = TemplateRequiredInVariantSuggestionSerializer(many=True)
    produces = FeatureProducedInVariantSuggestionSerializer(many=True)
    suggested_by = UserSerializer(many=False, read_only=True)

    class Meta:
        model = VariantSuggestion
        fields = [
            'id',
            'status',
            'notes',
            'uses',
            'requires',
            'produces',
            'mana_needed',
            'other_prerequisites',
            'description',
            'suggested_by',
        ]
        extra_kwargs = {
            'status': {'read_only': True},
        }

    def validate(self, attrs):
        VariantSuggestion.validate(
            [uses['card'] for uses in attrs['uses']],
            [requires['template'] for requires in attrs['requires']],
            [produce['feature'] for produce in attrs['produces']],
        )
        return super().validate(attrs)

    @transaction.atomic(durable=True)
    def create(self, validated_data):
        uses_key = 'uses'
        requires_key = 'requires'
        produces_key = 'produces'
        uses_set = validated_data.pop(uses_key)
        requires_set = validated_data.pop(requires_key)
        produces_set = validated_data.pop(produces_key)
        extended_kwargs = {
            'suggested_by': self.context['request'].user,
            **validated_data,
        }
        instance = super().create(extended_kwargs)
        for i, use in enumerate(uses_set):
            CardUsedInVariantSuggestion.objects.create(variant=instance, order=i, **use)
        for i, require in enumerate(requires_set):
            TemplateRequiredInVariantSuggestion.objects.create(variant=instance, order=i, **require)
        for produce in produces_set:
            FeatureProducedInVariantSuggestion.objects.create(variant=instance, **produce)
        return instance

    @transaction.atomic(durable=True)
    def update(self, instance, validated_data):
        uses_set = validated_data.pop('uses')
        requires_set = validated_data.pop('requires')
        produces_set = validated_data.pop('produces')
        extended_kwargs = {
            **validated_data,
        }
        instance = super().update(instance, extended_kwargs)
        instance.uses.all().delete()
        for i, use in enumerate(uses_set):
            CardUsedInVariantSuggestion.objects.create(variant=instance, order=i, **use)
        instance.requires.all().delete()
        for i, require in enumerate(requires_set):
            TemplateRequiredInVariantSuggestion.objects.create(variant=instance, order=i, **require)
        instance.produces.all().delete()
        for produce in produces_set:
            FeatureProducedInVariantSuggestion.objects.create(variant=instance, **produce)
        return instance

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[VariantSuggestion]):
        return queryset.prefetch_related(
            'uses',
            'requires',
            'produces',
            'suggested_by',
        )

    def to_internal_value(self, data: dict):
        description = data.get('description', None)
        if description is not None and isinstance(description, str):
            data['description'] = sanitize_apostrophes_and_quotes(description)
        other_prerequisites = data.get('other_prerequisites', None)
        if other_prerequisites is not None and isinstance(other_prerequisites, str):
            data['other_prerequisites'] = sanitize_apostrophes_and_quotes(other_prerequisites)
        return super().to_internal_value(data)
