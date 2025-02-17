from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from django.db.models import F, Sum, Case, When, Value, QuerySet
from django.db.models.functions import Greatest
from drf_spectacular.utils import extend_schema, inline_serializer
from spellbook.models import Card, CardInVariant, Variant, estimate_bracket
from spellbook.views import VariantViewSet
from website.views import PlainTextDeckListParser
from .utils import DecklistAPIView


class EstimateBracketView(DecklistAPIView):
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    response = inline_serializer(
        name='BracketEstimateResponse',
        fields={
            'bracket': serializers.IntegerField(allow_null=True),
            'bracket_explanation': serializers.CharField(allow_null=True, allow_blank=True),
        }
    )

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def get(self, request: Request) -> Response:
        deck = self.parse(request)
        cards = list(Card.objects.filter(pk__in=deck.cards.distinct_elements()))

        quantity_in_deck = Case(
            *(When(card_id=card_id, then=quantity) for card_id, quantity in deck.cards.items()),
            default=Value(0),
        )

        variant_id_list = CardInVariant.objects \
            .values('variant_id') \
            .alias(
                missing_count=Sum(Greatest(F('quantity') - quantity_in_deck, Value(0))),
            ) \
            .filter(
                missing_count__lte=0,
            )

        viewset = VariantViewSet()
        viewset.setup(self.request)
        variants_query: QuerySet[Variant] = viewset.filter_queryset(Variant.objects.filter(id__in=variant_id_list))
        variants = list(variants_query)

        bracket, explanation = estimate_bracket(cards, variants)

        return Response({
            'bracket': bracket,
            'bracket_explanation': explanation,
        })

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
