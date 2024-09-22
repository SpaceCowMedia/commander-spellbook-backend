from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance
from rest_framework import serializers
from .abstractions import Deck, CardInDeck, MAX_DECKLIST_LINES


class PaginationWrapper(serializers.BaseSerializer):
    def __init__(self, serializer_class, pagination_class, **kwargs):
        self.serializer_class = serializer_class
        self.pagination_class = pagination_class
        super().__init__(**kwargs)


class PaginationWrapperExtension(OpenApiSerializerExtension):
    target_class = PaginationWrapper

    def get_name(self, auto_schema, direction):
        return auto_schema.get_paginated_name(
            auto_schema._get_serializer_name(
                serializer=force_instance(self.target.serializer_class),
                direction=direction
            )
        )

    def map_serializer(self, auto_schema, direction):
        component = auto_schema.resolve_serializer(self.target.serializer_class, direction)
        paginated_schema = self.target.pagination_class().get_paginated_response_schema(component.ref)
        return paginated_schema


class CardInDeckSerializer(serializers.Serializer):
    card = serializers.CharField(max_length=500, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def create(self, validated_data):
        return CardInDeck(**validated_data)


class DeckSerializer(serializers.Serializer):
    MAX_COMMANDERS_LIST_LENGTH = MAX_DECKLIST_LINES // 100
    MAX_MAIN_LIST_LENGTH = MAX_DECKLIST_LINES - MAX_COMMANDERS_LIST_LENGTH
    main = serializers.ListField(child=CardInDeckSerializer(), max_length=MAX_MAIN_LIST_LENGTH, default=list)
    commanders = serializers.ListField(child=CardInDeckSerializer(), max_length=MAX_COMMANDERS_LIST_LENGTH, default=list)

    def create(self, validated_data):
        return Deck(
            main=[self.get_fields()['main'].child.create(item) for item in validated_data.get('main', [])],  # type: ignore
            commanders=[self.get_fields()['commanders'].child.create(item) for item in validated_data.get('commanders', [])]  # type: ignore
        )
