from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from django.db.models import F, Sum, Case, When, Value, QuerySet, Q
from django.db.models.functions import Greatest
from drf_spectacular.utils import extend_schema, OpenApiParameter
from spellbook.models import Card, CardInVariant, Variant, estimate_bracket
from spellbook.serializers import CardSerializer, VariantSerializer
from spellbook.views import VariantViewSet
from website.views import PlainTextDeckListParser
from .utils import DecklistAPIView


class EstimateBracketResultSerializer(serializers.Serializer):
    bracket = serializers.IntegerField()
    explanation = serializers.CharField(allow_blank=True)
    game_changers = serializers.ListField(child=CardSerializer())
    mass_land_denial = serializers.ListField(child=CardSerializer())
    extra_turn = serializers.ListField(child=CardSerializer())
    tutor = serializers.ListField(child=CardSerializer())
    two_card_combos = serializers.ListField(child=VariantSerializer())
    early_game_two_card_combos = serializers.ListField(child=VariantSerializer())


class EstimateBracketView(DecklistAPIView):
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    response = EstimateBracketResultSerializer
    parameters = [
        OpenApiParameter(name='single', type=bool, location=OpenApiParameter.QUERY, description='Whether to consider the decklist a single combo'),
    ]

    @extend_schema(request=DecklistAPIView.request, responses=response, parameters=parameters)
    def get(self, request: Request) -> Response:
        single = request.query_params.get('single', 'false').lower() == 'true'
        deck = self.parse(request)
        cards = list(Card.objects.filter(pk__in=deck.cards.distinct_elements()))

        quantity_in_deck = Case(
            *(When(card_id=card_id, then=quantity) for card_id, quantity in deck.cards.items()),
            default=Value(0),
        )

        quantity_in_command_zone = Case(
            *(When(card_id=card_id, then=quantity) for card_id, quantity in deck.commanders.items()),
            default=Value(0),
        )

        variant_id_list = CardInVariant.objects \
            .values('variant_id') \
            .alias(
                missing_count=Sum(Greatest(F('quantity') - quantity_in_deck, Value(0))),
                commander_missing_count=Sum(Greatest(F('quantity') - quantity_in_command_zone, Value(0))),
            ) \
            .filter(
                Q(missing_count=0, must_be_commander=False) | Q(commander_missing_count=0, must_be_commander=True)
            )

        viewset = VariantViewSet()
        viewset.setup(self.request)
        variants_query: QuerySet[Variant] = viewset.filter_queryset(viewset.get_queryset()).filter(id__in=variant_id_list).defer(None)
        variants = list(variants_query)

        result = estimate_bracket(cards, variants, single)
        serializer = self.response(result)
        return Response(serializer.data)

    @extend_schema(request=DecklistAPIView.request, responses=response, parameters=parameters)
    def post(self, request: Request) -> Response:
        return self.get(request)
