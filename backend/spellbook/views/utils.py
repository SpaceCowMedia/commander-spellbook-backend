from dataclasses import dataclass
from functools import cached_property
from typing import Sequence
from common.serializers import CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from django.db.models import F, Sum, Case, When, Count
from django.db.models.functions import Coalesce, Greatest
from rest_framework import parsers
from rest_framework.views import APIView
from rest_framework.request import Request
from common.serializers import DeckSerializer as RawDeckSerializer
from spellbook.models import Card, Template, Variant, merge_identities
from spellbook.variants.multiset import Multiset, FrozenMultiset
from website.views import PlainTextDeckListParser


@dataclass
class Deck:
    main: FrozenMultiset[int]
    commanders: FrozenMultiset[int]
    identity: str

    @cached_property
    def cards(self) -> FrozenMultiset[int]:
        return self.main.union(self.commanders)

    @cached_property
    def templates(self) -> FrozenMultiset[int]:
        template_id_list = Template.objects \
            .values('id') \
            .annotate(
                quantity_in_deck=Case(
                    When(scryfall_query__isnull=False, then=1),
                    default=Coalesce(
                        Sum(
                            Case(
                                *(
                                    When(templatereplacement__card_id=card_id, then=quantity)
                                    for card_id, quantity
                                    in self.cards.items()
                                ),
                                default=0,
                            ),
                        ),
                        1,
                    ),
                ),
            ) \
            .filter(
                quantity_in_deck__gte=1,
            ) \
            .values_list('id', 'quantity_in_deck')
        return FrozenMultiset[int]({template_id: quantity for template_id, quantity in template_id_list})


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
    identity = merge_identities(identity_dict[id] for id in cards.distinct_elements() if id in identity_dict)
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


def find_variants(deck: Deck) -> Sequence[str]:
    card_quantity_in_deck = Case(
        *(When(cardinvariant__card_id=card_id, then=quantity) for card_id, quantity in deck.cards.items()),
        default=0,
    )

    template_quantity_in_deck = Case(
        *(When(templateinvariant__template_id=template_id, then=quantity) for template_id, quantity in deck.templates.items()),
        default=0,
    )

    variant_id_list = Variant.objects \
        .values('pk') \
        .alias(
            missing_count=Coalesce(
                Sum(
                    Greatest(
                        F('cardinvariant__quantity') - card_quantity_in_deck,
                        0,
                    ),
                ),
                0,
            ) / Greatest(Count('templateinvariant', distinct=True), 1) + Coalesce(
                Sum(
                    Greatest(
                        F('templateinvariant__quantity') - template_quantity_in_deck,
                        0,
                    ),
                ),
                0,
            ) / Greatest(Count('cardinvariant', distinct=True), 1),
        ) \
        .filter(
            missing_count__lte=1,
        )

    return variant_id_list  # type: ignore
