from rest_framework import parsers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from rest_framework.settings import api_settings
from spellbook.models import Card, Variant, merge_identities
from spellbook.serializers import VariantSerializer
from dataclasses import dataclass
from .variants import VariantViewSet


@dataclass
class Deck:
    cards: set[int]
    commanders: set[int]


class PlainTextDeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def __init__(self):
        self.cards_dict: dict[str, int] = {name.lower(): id for name, id in Card.objects.values_list('name', 'id')}

    def parse(self, stream, media_type=None, parser_context=None) -> Deck:
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        lines = stream.read().decode(encoding).splitlines()[:500]
        main_cards = set[int]()
        commanders = set[int]()
        current_set = main_cards
        for line in lines:
            line: str = line.strip().lower()
            if not line:
                continue
            elif line.startswith('// command'):
                current_set = commanders
            elif line.startswith('//'):
                current_set = main_cards
            elif line in self.cards_dict:
                current_set.add(self.cards_dict[line])
        return Deck(cards=main_cards, commanders=commanders)


class JsonDeckListParser(parsers.JSONParser):
    def __init__(self):
        self.cards_dict: dict[str, int] = {name.lower(): id for name, id in Card.objects.values_list('name', 'id')}

    def parse(self, stream, media_type=None, parser_context=None) -> Deck:
        json: dict[str, list[str]] = super().parse(stream, media_type, parser_context)
        main_cards = set[int]()
        commanders = set[int]()
        for commander in json.get('commanders', [])[:500]:
            if isinstance(commander, str):
                commander = commander.strip().lower()
                if commander in self.cards_dict:
                    commanders.add(self.cards_dict[commander])
        for card in json.get('main', [])[:500]:
            if isinstance(card, str):
                card = card.strip().lower()
                if card in self.cards_dict:
                    main_cards.add(self.cards_dict[card])
        return Deck(cards=main_cards, commanders=commanders)


@api_view(http_method_names=['GET', 'POST'])
@parser_classes([JsonDeckListParser, PlainTextDeckListParser])
@permission_classes([AllowAny])
def find_my_combos(request: Request) -> Response:
    deck: Deck | dict = request.data
    if isinstance(deck, dict):
        deck = Deck(cards=set(), commanders=set())
    cards = deck.cards.union(deck.commanders)
    variant_to_cards = dict[Variant, set[int]]()
    variant_to_commanders = dict[Variant, set[int]]()
    variants_query = VariantViewSet.queryset \
        .filter(uses__in=cards) \
        .order_by('id')

    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    paginator = pagination_class()
    variants_page = paginator.paginate_queryset(variants_query, request)

    for v in variants_page:
        cards_in_variant = list(v.cardinvariant_set.all())
        variant_to_cards[v] = set(c.card_id for c in cards_in_variant)
        variant_to_commanders[v] = set(c.card_id for c in cards_in_variant if c.must_be_commander)
    included_variants = []
    included_variants_by_changing_commanders = []
    almost_included_variants = []
    almost_included_variants_by_adding_colors = []
    almost_included_variants_by_changing_commanders = []
    almost_included_variants_by_adding_colors_and_changing_commanders = []

    identity = merge_identities(identity for identity in Card.objects.filter(id__in=cards).values_list('identity', flat=True))
    identity_set = set(identity)

    for variant in variants_page:
        variant_data = VariantSerializer(variant).data
        variant_cards = variant_to_cards[variant]
        if variant_to_commanders[variant].issubset(deck.commanders):
            if variant_cards.issubset(cards):
                included_variants.append(variant_data)
            elif variant_cards.intersection(cards):
                if set(variant.identity).issubset(identity_set):
                    almost_included_variants.append(variant_data)
                else:
                    almost_included_variants_by_adding_colors.append(variant_data)
        elif variant_cards.issubset(cards):
            included_variants_by_changing_commanders.append(variant_data)
        elif variant_cards.intersection(cards):
            if set(variant.identity).issubset(identity_set):
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
