from collections import defaultdict
from django.db.models import Q
from rest_framework import parsers
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import AllowAny
from spellbook.models import Card, Variant, CardInVariant
from spellbook.variants.list_utils import merge_identities
from spellbook.serializers import VariantSerializer
from dataclasses import dataclass


@dataclass
class Deck:
    cards: set[Card]
    commanders: set[Card]


class PlainTextDeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def __init__(self):
        self.cards_dict = {c.name.lower(): c for c in Card.objects.all()}

    def parse(self, stream, media_type=None, parser_context=None) -> Deck:
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        lines = stream.read().decode(encoding).splitlines()[:500]
        main_cards = set[Card]()
        commanders = set[Card]()
        current_set = main_cards
        for line in lines:
            line: str = line.strip().lower()
            if not line:
                continue
            elif line.startswith('// Command'):
                current_set = commanders
            elif line.startswith('//'):
                current_set = main_cards
            elif line in self.cards_dict:
                current_set.add(self.cards_dict[line])
        return Deck(cards=main_cards, commanders=commanders)


class JsonDeckListParser(parsers.JSONParser):
    def __init__(self):
        self.cards_dict = {c.name.lower(): c for c in Card.objects.all()}

    def parse(self, stream, media_type=None, parser_context=None) -> Deck:
        json: dict[str, list[str]] = super().parse(stream, media_type, parser_context)
        main_cards = set[Card]()
        commanders = set[Card]()
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
    variant_to_cards = defaultdict[Variant, set[Card]](set)
    variants_query = CardInVariant.objects \
        .filter(variant__status=Variant.Status.OK, variant__uses__in=cards) \
        .prefetch_related(
            'card',
            'variant',
            'variant__cardinvariant_set__card',
            'variant__templateinvariant_set__template',
            'variant__cardinvariant_set',
            'variant__templateinvariant_set',
            'variant__produces',
            'variant__of',
            'variant__includes')
    if deck.commanders:
        variants_query = variants_query.exclude(~Q(variant__cardinvariant__card__in=deck.commanders), variant__cardinvariant__zone_locations=CardInVariant.ZoneLocation.COMMAND_ZONE)
    for civ in variants_query:
        variant_to_cards[civ.variant].add(civ.card)
    included_variants = []
    almost_included_variants = []
    almost_included_variants_by_adding_colors = []

    identity = merge_identities(c.identity for c in cards)
    identity_set = set(identity)

    for variant in variant_to_cards:
        if variant_to_cards[variant].issubset(cards):
            included_variants.append(VariantSerializer(variant).data)
        elif variant_to_cards[variant].intersection(cards):
            if set(variant.identity).issubset(identity_set):
                almost_included_variants.append(VariantSerializer(variant).data)
            else:
                almost_included_variants_by_adding_colors.append(VariantSerializer(variant).data)
    return Response({
        'identity': identity,
        'included': included_variants,
        'almost_included': almost_included_variants,
        'almost_included_by_adding_colors': almost_included_variants_by_adding_colors,
    })
