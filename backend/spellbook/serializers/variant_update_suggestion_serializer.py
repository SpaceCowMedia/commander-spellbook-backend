from django.db import transaction
from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import VariantInVariantUpdateSuggestion, VariantUpdateSuggestion, Variant
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes
from .user_serializer import UserSerializer
from .utils import ModelSerializerWithRelatedModels


class VariantInVariantUpdateSuggestionSerializer(serializers.ModelSerializer):
    variant = serializers.PrimaryKeyRelatedField(many=False, queryset=Variant.objects.filter(status__in=Variant.public_statuses()))

    class Meta:
        model = VariantInVariantUpdateSuggestion
        fields = [
            'variant',
            'issue',
        ]


class VariantUpdateSuggestionSerializer(serializers.ModelSerializer, ModelSerializerWithRelatedModels):
    variants = VariantInVariantUpdateSuggestionSerializer(many=True, required=False)
    suggested_by = UserSerializer(many=False, read_only=True)

    class Meta:
        model = VariantUpdateSuggestion
        fields = [
            'id',
            'status',
            'kind',
            'variants',
            'issue',
            'solution',
            'comment',
            'suggested_by',
            'created',
        ]
        extra_kwargs = {
            'status': {'read_only': True},
        }

    def validate(self, attrs: dict):
        VariantUpdateSuggestion.validate(
            [variant['variant'] for variant in attrs['variants']],
        )
        return super().validate(attrs)

    @transaction.atomic(durable=True)
    def create(self, validated_data: dict):
        variants_key = 'variants'
        variants_set = validated_data.pop(variants_key)
        extended_kwargs = {
            **validated_data,
            'suggested_by': self.context['request'].user,
        }
        instance = super().create(extended_kwargs)
        self._create_related_model(
            instance,
            VariantInVariantUpdateSuggestion.objects,
            VariantInVariantUpdateSuggestion.suggestion.field.name,
            variants_set,
            with_order=False,
        )
        return instance

    @transaction.atomic(durable=True)
    def update(self, instance: VariantUpdateSuggestion, validated_data: dict):
        variants_validated_data: list[dict] = validated_data.pop('variants', [])
        instance = super().update(instance, validated_data.copy())
        self._update_related_model(
            instance,
            instance.variants,
            VariantInVariantUpdateSuggestion.suggestion.field.name,
            variants_validated_data,
            self.fields['variants'].child,
            with_order=False,
        )
        return instance

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[VariantUpdateSuggestion]):
        return queryset.prefetch_related(
            'variants',
            'suggested_by',
        )

    def to_internal_value(self, data: dict):
        for variant in data.get('variants', []):
            if variant.get('issue'):
                variant['issue'] = sanitize_newlines_apostrophes_and_quotes(variant['issue'])
        if data.get('issue'):
            data['issue'] = sanitize_newlines_apostrophes_and_quotes(data['issue'])
        if data.get('solution'):
            data['solution'] = sanitize_newlines_apostrophes_and_quotes(data['solution'])
        if data.get('comment'):
            data['comment'] = sanitize_newlines_apostrophes_and_quotes(data['comment'])
        return super().to_internal_value(data)
