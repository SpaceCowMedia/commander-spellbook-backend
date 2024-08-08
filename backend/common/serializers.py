from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance
from rest_framework import serializers
from rest_framework_dataclasses.serializers import DataclassSerializer
from .abstractions import Deck


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


class DeckSerializer(DataclassSerializer):
    class Meta:
        dataclass = Deck
