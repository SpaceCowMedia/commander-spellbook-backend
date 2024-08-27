from dataclasses import dataclass
from multiset import FrozenMultiset, Multiset
from django.db.models import F, Sum, Case, When, Value
from django.db.models.functions import Greatest
from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema
from common.serializers import PaginationWrapper, DeckSerializer as RawDeckSerializer, CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from spellbook.models import Card, merge_identities, CardInVariant, Variant
from spellbook.serializers import VariantSerializer
from spellbook.views.variants import VariantViewSet
from spellbook.regexs.compiled import DECKLIST_LINE_REGEX


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


def raw_from_text(text: str) -> RawDeck:
    lines = text.splitlines()[:500]
    main = list[RawCardInDeck]()
    commanders = list[RawCardInDeck]()
    current_set = main
    for line in lines:
        line: str = line.strip().lower()
        if not line:
            continue
        elif line.startswith('// command') or line in ('commanders', 'commander', 'command', 'command zone'):
            current_set = commanders
        elif line.startswith('//') or line in ('main', 'deck'):
            current_set = main
        elif regex_match := DECKLIST_LINE_REGEX.fullmatch(line):
            current_set.append(RawCardInDeck(card=regex_match.group('card'), quantity=int(regex_match.group('quantity') or 1)))
    return RawDeck(main=main, commanders=commanders)


class PlainTextDeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None) -> RawDeck:
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        text = stream.read().decode(encoding)
        return raw_from_text(text)


class JsonDeckListParser(parsers.JSONParser):
    def parse(self, stream, media_type=None, parser_context=None) -> RawDeck:
        json: dict[str, list[str]] = super().parse(stream, media_type, parser_context)
        serializer: RawDeckSerializer = RawDeckSerializer(data=json)  # type: ignore
        serializer.is_valid(raise_exception=True)
        return serializer.save()


class FindMyComboResponseSerializer(serializers.Serializer):
    identity = serializers.CharField()
    included = VariantSerializer(many=True)
    included_by_changing_commanders = VariantSerializer(many=True)
    almost_included = VariantSerializer(many=True)
    almost_included_by_adding_colors = VariantSerializer(many=True)
    almost_included_by_changing_commanders = VariantSerializer(many=True)
    almost_included_by_adding_colors_and_changing_commanders = VariantSerializer(many=True)


class FindMyCombosView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [PlainTextDeckListParser, JsonDeckListParser]
    pagination_class = LimitOffsetPagination
    request = {
        'application/json': RawDeckSerializer,
        'text/plain': str,
    }
    response = PaginationWrapper(FindMyComboResponseSerializer, pagination_class)

    @extend_schema(request=request, responses=response)
    def get(self, request: Request) -> Response:
        raw_deck: RawDeck | dict = request.data  # type: ignore
        if isinstance(raw_deck, dict):
            raw_deck = RawDeck(main=[], commanders=[])
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
            .values('variant') \
            .alias(missing_count=Sum(Greatest(F('quantity') - quantity_in_deck, Value(0)))) \
            .filter(missing_count__lte=1)

        viewset = VariantViewSet()
        variants_query = viewset.get_queryset().filter(id__in=variant_id_list)

        paginator = self.pagination_class()
        paginator.max_limit = 1000  # type: ignore
        paginator.default_limit = 1000
        variants_page: list[Variant] = paginator.paginate_queryset(variants_query, request)  # type: ignore

        identity_set = set(identity) - {'C'}
        included_variants = []
        included_variants_by_changing_commanders = []
        almost_included_variants = []
        almost_included_variants_by_adding_colors = []
        almost_included_variants_by_changing_commanders = []
        almost_included_variants_by_adding_colors_and_changing_commanders = []

        for variant in variants_page:
            variant_data: dict = viewset.serializer_class(variant).data  # type: ignore
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

        return paginator.get_paginated_response({
            'identity': identity,
            'included': included_variants,
            'included_by_changing_commanders': included_variants_by_changing_commanders,
            'almost_included': almost_included_variants,
            'almost_included_by_adding_colors': almost_included_variants_by_adding_colors,
            'almost_included_by_changing_commanders': almost_included_variants_by_changing_commanders,
            'almost_included_by_adding_colors_and_changing_commanders': almost_included_variants_by_adding_colors_and_changing_commanders,
        })

    @extend_schema(request=request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
