from django.db import transaction
from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import CardUsedInVariantSuggestion, FeatureProducedInVariantSuggestion, TemplateRequiredInVariantSuggestion, VariantSuggestion, IngredientInCombination, ZoneLocation
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes, sanitize_mana, sanitize_scryfall_query
from .user_serializer import UserSerializer
from .utils import StringMultipleChoiceField


class IngredientInVariantSuggestionSerializer(serializers.ModelSerializer):
    zone_locations = StringMultipleChoiceField(choices=ZoneLocation.choices, allow_empty=False)

    def validate(self, attrs):
        IngredientInCombination.clean_data(attrs)
        return super().validate(attrs)


class CardUsedInVariantSuggestionSerializer(IngredientInVariantSuggestionSerializer):
    class Meta:
        model = CardUsedInVariantSuggestion
        fields = [
            'card',
            'quantity',
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
            'quantity',
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
            'spoiler',
            'comment',
            'suggested_by',
            'created',
        ]
        extra_kwargs = {
            'status': {'read_only': True},
        }

    def validate(self, attrs):
        VariantSuggestion.validate(
            [uses['card'] for uses in attrs['uses']],
            [requires['template'] for requires in attrs['requires']],
            [produce['feature'] for produce in attrs['produces']],
            ignore=self.instance.pk if self.instance else None,  # type: ignore
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
        for card in data.get('uses', []):
            if card.get('card'):
                card['card'] = sanitize_newlines_apostrophes_and_quotes(card['card'])
            if card.get('battlefield_card_state'):
                card['battlefield_card_state'] = sanitize_newlines_apostrophes_and_quotes(card['battlefield_card_state'])
            if card.get('exile_card_state'):
                card['exile_card_state'] = sanitize_newlines_apostrophes_and_quotes(card['exile_card_state'])
            if card.get('library_card_state'):
                card['library_card_state'] = sanitize_newlines_apostrophes_and_quotes(card['library_card_state'])
            if card.get('graveyard_card_state'):
                card['graveyard_card_state'] = sanitize_newlines_apostrophes_and_quotes(card['graveyard_card_state'])
        for template in data.get('requires', []):
            if template.get('template'):
                template['template'] = sanitize_newlines_apostrophes_and_quotes(template['template'])
            if template.get('scryfall_query'):
                template['scryfall_query'] = sanitize_scryfall_query(template['scryfall_query'])
            if template.get('battlefield_card_state'):
                template['battlefield_card_state'] = sanitize_newlines_apostrophes_and_quotes(template['battlefield_card_state'])
            if template.get('exile_card_state'):
                template['exile_card_state'] = sanitize_newlines_apostrophes_and_quotes(template['exile_card_state'])
            if template.get('library_card_state'):
                template['library_card_state'] = sanitize_newlines_apostrophes_and_quotes(template['library_card_state'])
            if template.get('graveyard_card_state'):
                template['graveyard_card_state'] = sanitize_newlines_apostrophes_and_quotes(template['graveyard_card_state'])
        for feature in data.get('produces', []):
            if feature.get('feature'):
                feature['feature'] = sanitize_newlines_apostrophes_and_quotes(feature['feature'])
        if data.get('description'):
            data['description'] = sanitize_newlines_apostrophes_and_quotes(data['description'])
        if data.get('notes'):
            data['notes'] = sanitize_newlines_apostrophes_and_quotes(data['notes'])
        if data.get('other_prerequisites'):
            data['other_prerequisites'] = sanitize_newlines_apostrophes_and_quotes(data['other_prerequisites'])
        if data.get('comment'):
            data['comment'] = sanitize_newlines_apostrophes_and_quotes(data['comment'])
        if data.get('mana_needed'):
            data['mana_needed'] = sanitize_mana(sanitize_newlines_apostrophes_and_quotes(data['mana_needed']))
        return super().to_internal_value(data)
