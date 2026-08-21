from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Iterable, Sequence
from common.serializers import CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from django.db.models import Case, F, Sum, When
from django.db.models.functions import Coalesce, Greatest
from django.template import loader
from djangorestframework_camel_case.render import CamelCaseBrowsableAPIRenderer
from rest_framework import parsers
from rest_framework.views import APIView
from rest_framework.request import Request
from common.serializers import DeckSerializer as RawDeckSerializer
from spellbook.models import Card, Template, TemplateInVariant, Variant, merge_color_identities
from spellbook.variants.multiset import Multiset, FrozenMultiset
from website.views import PlainTextDeckListParser


def quantity_in_deck(ingredient: str, deck: Iterable[tuple[int, int]]) -> Case:
    '''How many copies of the row's ingredient the deck holds, zero when it holds none.

    The ingredients are grouped by that quantity, so that the expression carries one branch per distinct
    quantity in the deck instead of one per ingredient, and every backend evaluates it as a handful of
    set memberships rather than a comparison per card.'''
    ids_by_quantity = defaultdict[int, list[int]](list)
    for id, quantity in deck:
        ids_by_quantity[quantity].append(id)
    return Case(
        *(When(**{f'{ingredient}__in': ids}, then=quantity) for quantity, ids in sorted(ids_by_quantity.items())),
        default=0,
    )


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
                        Sum(quantity_in_deck('templatereplacement__card_id', self.cards.items())),
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
    identity = merge_color_identities(identity_dict[id] for id in cards.distinct_elements() if id in identity_dict)
    return Deck(main=FrozenMultiset(main), commanders=FrozenMultiset(commanders), identity=identity)


class FilterFormBrowsableAPIRenderer(CamelCaseBrowsableAPIRenderer):
    '''
    The default renderer only builds the filter form for list views backed by a queryset,
    so plain API views need their filter backends to be rendered here instead.
    '''

    def get_filter_form(self, data, view, request):
        elements = [
            html
            for backend in getattr(view, 'filter_backends', [])
            if hasattr(backend, 'to_html') and (html := backend().to_html(request, None, view))
        ]
        if not elements:
            return None
        template = loader.get_template(self.filter_template)
        return template.render({'elements': elements})


class DecklistAPIView(APIView):
    permission_classes: list = []
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


def find_variants(deck: Deck, missing=1) -> Sequence[str]:
    '''The ids of the variants the deck is short of at most `missing` copies of an ingredient.

    The card side counts from Variant, not from CardInVariant, so that a variant asking for templates
    alone is still reached; the template side goes unnarrowed, so that too many missing templates stays
    distinct from none at all. A list, because as a subquery PostgreSQL re-runs it once per worker.'''
    missing_cards = dict[str, int](
        Variant.objects
        .values_list('pk')
        .order_by()
        .annotate(
            missing_count=Coalesce(
                Sum(
                    Greatest(
                        F('cardinvariant__quantity') - quantity_in_deck('cardinvariant__card_id', deck.cards.items()),
                        0,
                    ),
                ),
                0,
            ),
        )
        .filter(
            missing_count__lte=missing,
        )
        .values_list('pk', 'missing_count')
    )
    if not missing_cards:
        return []

    missing_templates = dict[str, int](
        TemplateInVariant.objects
        .values_list('variant_id')
        .order_by()
        .annotate(
            missing_count=Coalesce(
                Sum(
                    Greatest(
                        F('quantity') - quantity_in_deck('template_id', deck.templates.items()),
                        0,
                    ),
                ),
                0,
            ),
        )
        .values_list('variant_id', 'missing_count')
    )

    return [
        variant_id
        for variant_id, missing_count in missing_cards.items()
        if missing_count + missing_templates.get(variant_id, 0) <= missing
    ]
