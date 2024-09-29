import re
from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.plumbing import force_instance
from rest_framework import serializers
from .abstractions import Deck, CardInDeck


MAX_CARD_NAME_LENGTH = 256
MAX_DECKLIST_LINES = 600
DECKLIST_LINE_REGEX = r'^(?:(?P<quantity>\d{1,20})x?\s{1,6})?(?P<card>.*?[^\s])(?:(?:\s{1,6}<\w{1,50}>)?(?:\s{1,6}\[\w{1,50}\](?:\s{1,6}\(\w{1,50}\))?|\s{1,6}\(\w{1,50}\)(?:\s[\w-]+(?:\s\*\w\*)?)?))?$'
DECKLIST_LINE_PARSER = re.compile(DECKLIST_LINE_REGEX)


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
    card = serializers.CharField(max_length=MAX_CARD_NAME_LENGTH, allow_blank=True)
    quantity = serializers.IntegerField(min_value=1, default=1)

    def create(self, validated_data):
        return CardInDeck(**validated_data)


class DeckSerializer(serializers.Serializer):
    MAX_COMMANDERS_LIST_LENGTH = MAX_DECKLIST_LINES // 100
    MAX_MAIN_LIST_LENGTH = MAX_DECKLIST_LINES
    main = serializers.ListField(child=CardInDeckSerializer(), max_length=MAX_MAIN_LIST_LENGTH, default=list)
    commanders = serializers.ListField(child=CardInDeckSerializer(), max_length=MAX_COMMANDERS_LIST_LENGTH, default=list)

    def to_internal_value(self, data):
        if isinstance(data, str):
            lines = data.splitlines()
            main = dict[str, dict[str, object]]()
            commanders = dict[str, dict[str, object]]()
            current_set = main
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                if line_lower.startswith('// command') or line_lower in ('commanders', 'commander', 'command', 'command zone'):
                    current_set = commanders
                elif line_lower.startswith('//') or line_lower in ('main', 'deck'):
                    current_set = main
                elif regex_match := DECKLIST_LINE_PARSER.fullmatch(line):
                    card_name = regex_match.group('card').strip()
                    previous = current_set.setdefault(card_name, {'card': card_name, 'quantity': 0, })
                    previous['quantity'] += int(regex_match.group('quantity') or 1)  # type: ignore
            data = {'main': main.values(), 'commanders': commanders.values(), }
        return super().to_internal_value(data)

    def create(self, validated_data):
        return Deck(
            main=[self.get_fields()['main'].child.create(item) for item in validated_data.get('main', [])],  # type: ignore
            commanders=[self.get_fields()['commanders'].child.create(item) for item in validated_data.get('commanders', [])]  # type: ignore
        )
