from collections import defaultdict
from django.db import transaction
from django.db.models import QuerySet, Model
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from rest_framework import serializers
from spellbook.models import Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, CardInVariant, TemplateInVariant, VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion, IngredientInCombination
from spellbook.utils import convert_validation_exception


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'legal', 'spoiler']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description', 'utility']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Feature]):
        return queryset.all()


class CardDetailSerializer(serializers.ModelSerializer):
    features = FeatureSerializer(many=True, read_only=True)

    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'legal', 'spoiler', 'features']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Card]):
        return queryset.prefetch_related('features')


class TemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Template
        fields = ['id', 'name', 'scryfall_query', 'scryfall_api']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Template]):
        return queryset.all()


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


class ComboSerializer(serializers.ModelSerializer):
    class Meta:
        model = Combo
        fields = ['id']


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


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)
    mana_needed = serializers.SerializerMethodField()
    other_prerequisites = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_mana_needed(self, obj):
        if obj.status != Variant.Status.OK:
            return None
        return obj.mana_needed

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
            'other_prerequisites',
            'description',
            'legal',
            'spoiler',
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


class StringMultipleChoiceField(serializers.MultipleChoiceField):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.keys = {k: i for i, k in enumerate(self.choices.keys())}

    def to_internal_value(self, data):
        choices = {choice for choice in super().to_internal_value(data) if choice is not None}
        return ''.join(sorted(choices, key=lambda x: self.keys[x]))

    def to_representation(self, value):
        return list(sorted(super().to_representation(value), key=lambda x: self.keys[x]))


class IngredientInVariantSuggestionSerializer(serializers.ModelSerializer):
    zone_locations = StringMultipleChoiceField(choices=IngredientInCombination.ZoneLocation.choices, allow_empty=False)


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
        try:
            VariantSuggestion.validate(
                [uses['card'] for uses in uses_set],
                [requires['template'] for requires in requires_set],
                [produce['feature'] for produce in produces_set],
            )
        except ValidationError as exc:
            raise convert_validation_exception(exc)
        children : defaultdict[str, list[Model]] = defaultdict(list)
        instance = super().create(extended_kwargs)
        for i, use in enumerate(uses_set):
            child = CardUsedInVariantSuggestion(variant=instance, order=i, **use)
            children[uses_key].append(child)
        for i, require in enumerate(requires_set):
            child = TemplateRequiredInVariantSuggestion(variant=instance, order=i, **require)
            children[requires_key].append(child)
        for produce in produces_set:
            child = FeatureProducedInVariantSuggestion(variant=instance, **produce)
            children[produces_key].append(child)
        errors: defaultdict[str, list[ValidationError]] = defaultdict(list)
        for key, childldren in children.items():
            for child in childldren:
                try:
                    child.full_clean()
                    errors[key].append(None)
                except ValidationError as exc:
                    errors[key].append(exc)
        if errors:
            raise convert_validation_exception(errors)
        for child in children:
            child.save()
        return instance

    @transaction.atomic(durable=True)
    def update(self, instance, validated_data):
        uses_set = validated_data.pop('uses')
        requires_set = validated_data.pop('requires')
        produces_set = validated_data.pop('produces')
        extended_kwargs = {
            **validated_data,
        }
        try:
            VariantSuggestion.validate(
                [uses['card'] for uses in uses_set],
                [requires['template'] for requires in requires_set],
                [produce['feature'] for produce in produces_set],
            )
        except ValidationError as exc:
            raise convert_validation_exception(exc)
        children: list[Model] = []
        instance = super().update(instance, extended_kwargs)
        for i, use in enumerate(uses_set):
            child = CardUsedInVariantSuggestion(variant=instance, order=i, **use)
            children.append(child)
        for i, require in enumerate(requires_set):
            child = TemplateRequiredInVariantSuggestion(variant=instance, order=i, **require)
            children.append(child)
        for produce in produces_set:
            child = FeatureProducedInVariantSuggestion(variant=instance, **produce)
            children.append(child)
        errors = []
        for child in children:
            try:
                child.full_clean()
            except ValidationError as exc:
                errors.append(exc)
        if errors:
            raise convert_validation_exception(errors)
        instance.uses.all().delete()
        instance.requires.all().delete()
        instance.produces.all().delete()
        for child in children:
            child.save()
        return instance

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[VariantSuggestion]):
        return queryset.prefetch_related(
            'uses',
            'requires',
            'produces',
            'suggested_by',
        )
