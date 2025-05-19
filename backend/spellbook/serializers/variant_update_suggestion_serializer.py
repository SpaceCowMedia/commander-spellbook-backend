from itertools import zip_longest
from django.db import transaction
from django.db.models import QuerySet
from rest_framework import serializers
from spellbook.models import VariantInVariantUpdateSuggestion, VariantUpdateSuggestion, Variant
from spellbook.models.utils import sanitize_newlines_apostrophes_and_quotes
from .user_serializer import UserSerializer


class VariantInVariantUpdateSuggestionSerializer(serializers.ModelSerializer):
    variant = serializers.PrimaryKeyRelatedField(many=False, queryset=Variant.objects.filter(status__in=Variant.public_statuses()))

    class Meta:
        model = VariantInVariantUpdateSuggestion
        fields = [
            'variant',
            'issue',
        ]


class VariantUpdateSuggestionSerializer(serializers.ModelSerializer):
    variants = VariantInVariantUpdateSuggestionSerializer(many=True, required=False)
    suggested_by = UserSerializer(many=False, read_only=True)

    class Meta:
        model = VariantUpdateSuggestion
        fields = [
            'id',
            'status',
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
        for variant in variants_set:
            VariantInVariantUpdateSuggestion.objects.create(suggestion=instance, **variant)
        return instance

    @transaction.atomic(durable=True)
    def update(self, instance: VariantUpdateSuggestion, validated_data: dict):
        variants_validated_data: list[dict] = validated_data.pop('variants', [])
        instance = super().update(instance, validated_data.copy())
        variants_to_create: list[VariantInVariantUpdateSuggestion] = []
        variants_to_update: list[VariantInVariantUpdateSuggestion] = []
        variants_to_delete: list[VariantInVariantUpdateSuggestion] = []
        for d, model in zip_longest(variants_validated_data, instance.variants.all()):
            if model is None:
                variants_to_create.append(VariantInVariantUpdateSuggestion(**d, suggestion=instance))
            elif d is None:
                variants_to_delete.append(model)
            else:
                for key, value in d.items():
                    setattr(model, key, value)
                variants_to_update.append(model)
        VariantInVariantUpdateSuggestion.objects.bulk_create(variants_to_create)
        VariantInVariantUpdateSuggestion.objects.bulk_update(variants_to_update, self.fields['variants'].child.fields.keys())
        VariantInVariantUpdateSuggestion.objects.filter(pk__in=(model.pk for model in variants_to_delete)).delete()
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
