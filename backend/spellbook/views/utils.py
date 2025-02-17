from dataclasses import dataclass
from functools import cached_property
from multiset import FrozenMultiset, Multiset
from common.serializers import CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from rest_framework.views import APIView
from rest_framework import parsers
from common.serializers import DeckSerializer as RawDeckSerializer
from spellbook.models import Card, merge_identities
from website.views import PlainTextDeckListParser
from rest_framework.request import Request


@dataclass
class Deck:
    main: FrozenMultiset[int]
    commanders: FrozenMultiset[int]
    identity: str

    @cached_property
    def cards(self) -> FrozenMultiset[int]:
        return self.main.union(self.commanders)


def deck_from_raw(raw_deck: RawDeck, cards_id_dict: dict[str, int], identity_dict: dict[int, str]) -> Deck:
    valid_card_ids: set[int] = set(cards_id_dict.values())
    main = Multiset[int]()
    commanders = Multiset[int]()

    def next_card(raw_card: RawCardInDeck, card_set: Multiset[int]):
        card = raw_card.card.strip().lower()
        quantity = raw_card.quantity
        if not card or quantity < 1:
            return
        if card in cards_id_dict:
            card_set.add(cards_id_dict[card], quantity)
        elif card.isdigit():
            card_id = int(card)
            if card_id in valid_card_ids:
                card_set.add(card_id, quantity)
    for card in raw_deck.main:
        next_card(card, main)
    for commander in raw_deck.commanders:
        next_card(commander, commanders)
    cards = main.union(commanders)
    identity = merge_identities(identity_dict[id] for id in cards if id in identity_dict)
    return Deck(main=FrozenMultiset(main), commanders=FrozenMultiset(commanders), identity=identity)


class DecklistAPIView(APIView):
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    request = {
        'application/json': RawDeckSerializer,
        'text/plain': str,
    }

    def parse(self, request: Request) -> Deck:
        data: str | dict = request.data  # type: ignore
        serializer = RawDeckSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        raw_deck: RawDeck = serializer.save()  # type: ignore
        cards_data = list[tuple[str, int, str]](Card.objects.values_list('name', 'id', 'identity'))
        cards_data_dict: dict[str, int] = {name.lower(): id for name, id, _ in cards_data}
        cards_identity_dict: dict[int, str] = {id: identity for _, id, identity in cards_data}
        del cards_data
        deck = deck_from_raw(raw_deck, cards_data_dict, cards_identity_dict)
        return deck
