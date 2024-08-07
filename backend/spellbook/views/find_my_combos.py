from django.db.models import Count, Q, F
from rest_framework import parsers, serializers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from rest_framework.settings import api_settings
from drf_spectacular.utils import extend_schema, inline_serializer
from spellbook.models import Card, merge_identities, CardInVariant
from spellbook.serializers import VariantSerializer
from dataclasses import dataclass
from spellbook.views.variants import VariantViewSet


@dataclass
class Deck:
    cards: set[int]
    commanders: set[int]


@dataclass
class RawDeck:
    cards: list[str]
    commanders: list[str]

    def to_deck(self, cards_dict: dict[str, int]) -> Deck:
        valid_card_ids: set[int] = set(cards_dict.values())
        cards = set[int]()
        commanders = set[int]()

        def next_card(line: str, card_set: set[int]):
            if line in cards_dict:
                card_set.add(cards_dict[line])
            elif line.isdigit():
                card_id = int(line)
                if card_id in valid_card_ids:
                    card_set.add(card_id)
        for card in self.cards:
            next_card(card, cards)
        for commander in self.commanders:
            next_card(commander, commanders)
        return Deck(cards=cards, commanders=commanders)


class PlainTextDeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None) -> RawDeck:
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        lines = stream.read().decode(encoding).splitlines()[:500]
        main_cards = list[str]()
        commanders = list[str]()
        current_set = main_cards
        for line in lines:
            line: str = line.strip().lower()
            if not line:
                continue
            elif line.startswith('// command'):
                current_set = commanders
            elif line.startswith('//'):
                current_set = main_cards
            else:
                current_set.append(line)
        return RawDeck(cards=main_cards, commanders=commanders)


class JsonDeckListParser(parsers.JSONParser):
    def parse(self, stream, media_type=None, parser_context=None) -> RawDeck:
        json: dict[str, list[str]] = super().parse(stream, media_type, parser_context)
        main_cards = list[str]()
        commanders = list[str]()
        commanders_json = json.get('commanders', [])
        if isinstance(commanders_json, list):
            for commander in commanders_json[:500]:
                if isinstance(commander, str):
                    commander = commander.strip().lower()
                    commanders.append(commander)
        main_json = json.get('main', [])
        if isinstance(main_json, list):
            for card in main_json[:500]:
                if isinstance(card, str):
                    card = card.strip().lower()
                    main_cards.append(card)
        return RawDeck(cards=main_cards, commanders=commanders)


@extend_schema(
    request={
        'application/json': inline_serializer(
            name='FindMyCombosRequest',
            fields={
                'main': serializers.ListField(child=serializers.CharField(), max_length=500),
                'commanders': serializers.ListField(child=serializers.CharField(), max_length=500),
            }
        ),
        'text/plain': str,
    },
    responses=inline_serializer(
        name='FindMyCombosResult',
        fields={
            'identity': serializers.CharField(),
            'included': VariantSerializer(many=True),
        }
    ),
)
@api_view(http_method_names=['GET', 'POST'])
@parser_classes([JsonDeckListParser, PlainTextDeckListParser])
@permission_classes([AllowAny])
def find_my_combos(request: Request) -> Response:
    raw_deck: RawDeck | dict = request.data  # type: ignore
    if isinstance(raw_deck, dict):
        raw_deck = RawDeck(cards=list(), commanders=list())
    cards_data = Card.objects.values_list('name', 'id', 'identity')
    cards_data_dict: dict[str, int] = {name.lower(): id for name, id, _ in cards_data}
    deck = raw_deck.to_deck(cards_data_dict)
    cards = deck.cards.union(deck.commanders)
    identity = merge_identities(identity for _, id, identity in cards_data if id in cards)

    variant_id_list = CardInVariant.objects \
        .values('variant') \
        .alias(
            present_count=Count('variant', filter=Q(card_id__in=cards)) + 1,
            total_count=Count('variant')
        ) \
        .filter(present_count__gte=F('total_count'))
    viewset = VariantViewSet()
    variants_query = viewset.get_queryset().filter(id__in=variant_id_list)

    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    paginator = pagination_class()  # type: ignore
    paginator.max_limit = 1000
    paginator.default_limit = 1000
    variants_page = paginator.paginate_queryset(variants_query, request)

    identity_set = set(identity) - {'C'}
    included_variants = []
    included_variants_by_changing_commanders = []
    almost_included_variants = []
    almost_included_variants_by_adding_colors = []
    almost_included_variants_by_changing_commanders = []
    almost_included_variants_by_adding_colors_and_changing_commanders = []

    for variant in variants_page:
        variant_data: dict = viewset.serializer_class(variant).data  # type: ignore
        variant_cards = {civ['card']['id'] for civ in variant_data['uses']}
        variant_commanders = {civ['card']['id'] for civ in variant_data['uses'] if civ['must_be_commander']}
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
