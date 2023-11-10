from django.db import transaction
from django.db.models import QuerySet
from django.contrib.auth.models import User
from rest_framework import serializers
from spellbook.models import Playable, Card, Template, Feature, Combo, CardInCombo, TemplateInCombo, Variant, CardInVariant, TemplateInVariant, VariantSuggestion, CardUsedInVariantSuggestion, TemplateRequiredInVariantSuggestion, FeatureProducedInVariantSuggestion, IngredientInCombination


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username']


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'name', 'oracle_id', 'identity', 'spoiler']


class FeatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feature
        fields = ['id', 'name', 'description', 'utility']

    @classmethod
    def prefetch_related(cls, queryset: QuerySet[Feature]):
        return queryset.all()


class LegalitiesSerializer(serializers.ModelSerializer):
    commander = serializers.BooleanField(source='legal_commander')
    pauper_commander_main = serializers.BooleanField(source='legal_pauper_commander_main')
    pauper_commander_commander = serializers.BooleanField(source='legal_pauper_commander_commander')
    oathbreaker = serializers.BooleanField(source='legal_oathbreaker')
    predh = serializers.BooleanField(source='legal_predh')
    brawl = serializers.BooleanField(source='legal_brawl')
    vintage = serializers.BooleanField(source='legal_vintage')
    legacy = serializers.BooleanField(source='legal_legacy')
    modern = serializers.BooleanField(source='legal_modern')
    pioneer = serializers.BooleanField(source='legal_pioneer')
    standard = serializers.BooleanField(source='legal_standard')
    pauper = serializers.BooleanField(source='legal_pauper')

    class Meta:
        abstract = True
        model = Playable
        fields = [
            'commander',
            'pauper_commander_main',
            'pauper_commander_commander',
            'oathbreaker',
            'predh',
            'brawl',
            'vintage',
            'legacy',
            'modern',
            'pioneer',
            'standard',
            'pauper',
        ]


class PricesSerializer(serializers.ModelSerializer):
    tcgplayer = serializers.DecimalField(source='price_tcgplayer', max_digits=10, decimal_places=2)
    cardkingdom = serializers.DecimalField(source='price_cardkingdom', max_digits=10, decimal_places=2)
    cardmarket = serializers.DecimalField(source='price_cardmarket', max_digits=10, decimal_places=2)

    class Meta:
        model = Playable
        fields = [
            'tcgplayer',
            'cardkingdom',
            'cardmarket',
        ]


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


class VariantLegalitiesSerializer(LegalitiesSerializer):
    class Meta(LegalitiesSerializer.Meta):
        model = Variant


class VariantPricesSerializer(PricesSerializer):
    class Meta(PricesSerializer.Meta):
        model = Variant


class VariantSerializer(serializers.ModelSerializer):
    uses = CardInVariantSerializer(source='cardinvariant_set', many=True, read_only=True)
    requires = TemplateInVariantSerializer(source='templateinvariant_set', many=True, read_only=True)
    produces = FeatureSerializer(many=True, read_only=True)
    of = ComboSerializer(many=True, read_only=True)
    includes = ComboSerializer(many=True, read_only=True)
    mana_needed = serializers.SerializerMethodField()
    other_prerequisites = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    legalities = VariantLegalitiesSerializer(source='*', read_only=True)
    prices = VariantPricesSerializer(source='*', read_only=True)

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
            'spoiler',
            'legalities',
            'prices',
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
