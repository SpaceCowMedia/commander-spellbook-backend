from dataclasses import dataclass
from drf_spectacular.openapi import AutoSchema
from multiset import FrozenMultiset, Multiset
from django.db.models import F, Sum, Case, When, Value
from django.db.models.functions import Greatest
from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema, Direction
from drf_spectacular.extensions import OpenApiSerializerExtension
from common.serializers import DeckSerializer as RawDeckSerializer, CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from spellbook.models import Card, merge_identities, CardInVariant, Variant
from spellbook.models.mixins import PreSerializedSerializer
from spellbook.serializers import VariantSerializer
from website.views import PlainTextDeckListParser
from .variants import VariantViewSet


@dataclass
class Deck:
    main: FrozenMultiset[int]
    commanders: FrozenMultiset[int]


def deck_from_raw(raw_deck: RawDeck, cards_dict: dict[str, int]) -> Deck:
    valid_card_ids: set[int] = set(cards_dict.values())
    main = Multiset[int]()
    commanders = Multiset[int]()

    def next_card(raw_card: RawCardInDeck, card_set: Multiset[int]):
        card = raw_card.card.strip().lower()
        quantity = raw_card.quantity
        if not card or quantity < 1:
            return
        if card in cards_dict:
            card_set.add(cards_dict[card], quantity)
        elif card.isdigit():
            card_id = int(card)
            if card_id in valid_card_ids:
                card_set.add(card_id, quantity)
    for card in raw_deck.main:
        next_card(card, main)
    for commander in raw_deck.commanders:
        next_card(commander, commanders)
    return Deck(main=FrozenMultiset(main), commanders=FrozenMultiset(commanders))


class JsonDeckListParser(parsers.JSONParser):
    def parse(self, stream, media_type=None, parser_context=None) -> dict:
        json: dict[str, list[str]] = super().parse(stream, media_type, parser_context)
        return json


class FindMyCombosResponseSerializer(serializers.BaseSerializer):
    child = PreSerializedSerializer()
    variant_list_serializer = serializers.ListSerializer(child=child)

    def __new__(cls, *args, **kwargs):
        kwargs['many'] = False
        return super().__new__(cls, *args, **kwargs)

    def to_internal_value(self, data):
        return {
            'variants': self.variant_list_serializer.to_internal_value(data.get('variants', [])),
            'identity': data['identity'],
            'deck': data['deck'],
        }

    def to_representation(self, data):
        identity = data['identity']
        identity_set = set(identity) - {'C'}
        deck: Deck = data['deck']
        cards = deck.main.union(deck.commanders)
        included_variants = []
        included_variants_by_changing_commanders = []
        almost_included_variants = []
        almost_included_variants_by_adding_colors = []
        almost_included_variants_by_changing_commanders = []
        almost_included_variants_by_adding_colors_and_changing_commanders = []
        variants = self.variant_list_serializer.to_representation(data['variants'])
        for variant in variants:
            variant_data: dict = variant
            variant_cards = FrozenMultiset[int]({civ['card']['id']: civ['quantity'] for civ in variant_data['uses']})
            variant_commanders = FrozenMultiset[int]({civ['card']['id']: civ['quantity'] for civ in variant_data['uses'] if civ['must_be_commander']})
            variant_identity = set(variant_data['identity']) - {'C'}
            if variant_commanders.issubset(deck.commanders):
                if variant_cards.issubset(cards):
                    included_variants.append(variant_data)
                elif variant_cards.intersection(cards):
                    if set(variant_identity).issubset(identity_set):
                        almost_included_variants.append(variant_data)
                    else:
                        almost_included_variants_by_adding_colors.append(variant_data)
            elif variant_cards.issubset(cards):
                included_variants_by_changing_commanders.append(variant_data)
            elif variant_cards.intersection(cards):
                if set(variant_identity).issubset(identity_set):
                    almost_included_variants_by_changing_commanders.append(variant_data)
                else:
                    almost_included_variants_by_adding_colors_and_changing_commanders.append(variant_data)

        return {
            'identity': identity,
            'included': included_variants,
            'included_by_changing_commanders': included_variants_by_changing_commanders,
            'almost_included': almost_included_variants,
            'almost_included_by_adding_colors': almost_included_variants_by_adding_colors,
            'almost_included_by_changing_commanders': almost_included_variants_by_changing_commanders,
            'almost_included_by_adding_colors_and_changing_commanders': almost_included_variants_by_adding_colors_and_changing_commanders,
        }


class FindMyCombosResponseSerializerExtension(OpenApiSerializerExtension):
    target_class = FindMyCombosResponseSerializer

    def get_name(self, auto_schema: AutoSchema, direction: Direction) -> str | None:
        return 'FindMyCombosResponse'

    def map_serializer(self, auto_schema: AutoSchema, direction: Direction) -> dict[str, object]:
        required_properties = {
            'identity': auto_schema._map_serializer_field(serializers.CharField(), direction),
            'included': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'included_by_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_adding_colors': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_adding_colors_and_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
        }
        return {
            'type': 'object',
            'properties': required_properties,
            'required': sorted(required_properties),
        }


class FindMyCombosView(APIView):
    action = 'list'
    permission_classes = [AllowAny]
    parser_classes = [PlainTextDeckListParser, JsonDeckListParser]
    pagination_class = LimitOffsetPagination
    request = {
        'application/json': RawDeckSerializer,
        'text/plain': str,
    }
    response = FindMyCombosResponseSerializer
    filter_backends = VariantViewSet.filter_backends

    @extend_schema(request=request, responses=response)
    def get(self, request: Request) -> Response:
        data: str | dict = request.data  # type: ignore
        serializer = RawDeckSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        raw_deck: RawDeck = serializer.save()  # type: ignore
        cards_data = list(Card.objects.values_list('name', 'id', 'identity'))
        cards_data_dict: dict[str, int] = {name.lower(): id for name, id, _ in cards_data}
        deck = deck_from_raw(raw_deck, cards_data_dict)
        cards = deck.main.union(deck.commanders)
        identity = merge_identities(identity for _, id, identity in cards_data if id in cards)

        quantity_in_deck = Case(
            *(When(card_id=card_id, then=quantity) for card_id, quantity in cards.items()),
            default=Value(0),
        )

        variant_id_list = CardInVariant.objects \
            .values('variant_id') \
            .alias(missing_count=Sum(Greatest(F('quantity') - quantity_in_deck, Value(0)))) \
            .filter(missing_count__lte=1)

        viewset = VariantViewSet()
        viewset.setup(self.request)
        variants_query = viewset.filter_queryset(viewset.get_queryset().filter(id__in=variant_id_list))

        paginator = self.pagination_class()
        paginator.max_limit = 1000  # type: ignore
        paginator.default_limit = 1000
        variants_page: list[Variant] = paginator.paginate_queryset(variants_query, request)  # type: ignore
        return paginator.get_paginated_response(FindMyCombosResponseSerializer({
            'variants': variants_page,
            'identity': identity,
            'deck': deck,
        }).data)

    @extend_schema(request=request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
