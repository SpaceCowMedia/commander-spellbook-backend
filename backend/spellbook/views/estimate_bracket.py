from django.db.models import QuerySet
from djangorestframework_camel_case.render import CamelCaseJSONRenderer
from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema, OpenApiParameter
from spellbook.models import Card, Variant, estimate_bracket
from spellbook.serializers import CardSerializer, VariantSerializer, BracketTagSerializer
from website.views import PlainTextDeckListParser
from .filters import AbstractBooleanFilter
from .utils import DecklistAPIView, FilterFormBrowsableAPIRenderer, find_variants


class ClassifiedCardSerializer(serializers.Serializer):
    card = CardSerializer()
    quantity = serializers.IntegerField()
    banned = serializers.BooleanField()
    game_changer = serializers.BooleanField()
    mass_land_denial = serializers.BooleanField()
    extra_turn = serializers.BooleanField()


class ClassifiedVariantSerializer(serializers.Serializer):
    combo = VariantSerializer()
    relevant = serializers.BooleanField()
    borderline_relevant = serializers.BooleanField()
    arguably_two_card = serializers.BooleanField()
    definitely_two_card = serializers.BooleanField()
    speed = serializers.IntegerField()
    mass_land_denial = serializers.BooleanField()
    extra_turn = serializers.BooleanField()
    lock = serializers.BooleanField()
    skip_turns = serializers.BooleanField()
    control_all_opponents = serializers.BooleanField()
    control_some_opponents = serializers.BooleanField()


class EstimateBracketResultSerializer(serializers.Serializer):
    bracket_tag = BracketTagSerializer()
    cards = serializers.ListField(child=ClassifiedCardSerializer())
    combos = serializers.ListField(child=ClassifiedVariantSerializer())


class UnknownCommandersFilter(AbstractBooleanFilter):
    query_param = 'unknown_commanders'
    title = 'Unknown commanders'
    description = 'When true, an empty commander list is treated as unknown commanders instead of no commanders.'
    enabled_label = 'Treat missing commanders as unknown'
    disabled_label = 'Treat missing commanders as absent'


class EstimateBracketView(DecklistAPIView):
    permission_classes: list = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    renderer_classes = [CamelCaseJSONRenderer, FilterFormBrowsableAPIRenderer]
    filter_backends = [UnknownCommandersFilter]
    response = EstimateBracketResultSerializer
    parameters = [
        OpenApiParameter(
            name=UnknownCommandersFilter.query_param,
            type=bool,
            required=False,
            description=UnknownCommandersFilter.description,
        ),
    ]

    def deck_cards(self) -> QuerySet[Card]:
        # the whole row: these cards are classified and serialized back, so reading them narrower here
        # would only cost a second read of the same rows
        return Card.objects.all()

    @extend_schema(request=DecklistAPIView.request, parameters=parameters, responses=response)
    def get(self, request: Request) -> Response:
        deck = self.parse(request)
        unknown_commanders = UnknownCommandersFilter().is_enabled(request)
        cards: dict[Card, int] = dict(deck.cards.items())
        commanders: set[Card] | None = set(deck.commanders.distinct_elements())
        if unknown_commanders and not commanders:
            commanders = None
        variant_id_list = find_variants(deck, missing=0)
        variants_query = Variant.recipes_prefetched \
            .filter(status__in=Variant.public_statuses()) \
            .filter(id__in=variant_id_list)
        included_variants = [(v, v.get_recipe()) for v in variants_query]
        if commanders is not None:
            # a combo that needs another commander is only included by changing commanders
            included_variants = [
                (v, recipe)
                for v, recipe in included_variants
                if all(card in commanders for card_in_variant, card in recipe.cards if card_in_variant.must_be_commander)
            ]

        result = estimate_bracket(
            cards=cards,
            commanders=commanders,
            included_variants=included_variants,
        )
        serializer = self.response(result)
        return Response(serializer.data)

    @extend_schema(request=DecklistAPIView.request, parameters=parameters, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
