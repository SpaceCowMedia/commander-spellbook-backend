from collections import defaultdict
from dataclasses import dataclass
from itertools import chain
from functools import cached_property
from typing import Iterable, Sequence
from common.serializers import CardInDeck as RawCardInDeck
from common.abstractions import Deck as RawDeck
from django.db.models import Case, F, Q, QuerySet, Sum, When
from django.db.models.functions import Coalesce, Greatest, Lower
from django.template import loader
from djangorestframework_camel_case.render import CamelCaseBrowsableAPIRenderer
from rest_framework import parsers
from rest_framework.views import APIView
from rest_framework.request import Request
from common.serializers import DeckSerializer as RawDeckSerializer
from spellbook.models import Card, Template, TemplateInVariant, Variant, merge_color_identities, strip_accents
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


def card_numbers(cards: FrozenMultiset[Card]) -> FrozenMultiset[int]:
    '''The same cards in the id space the variants are built out of, without the ones not curated.'''
    return FrozenMultiset[int]({card.number: quantity for card, quantity in cards.items() if card.number is not None})


@dataclass
class Deck:
    '''A decklist resolved against the card table, holding the rows it named.

    Every card the list names is here, not only the ones an editor curated: a card no combo uses still
    decides the colours of the deck, whether it holds something banned, and which templates it matches.
    The variants are looked up by `used_cards`, the same cards keyed by the number a variant is built
    out of, which only a curated card has.'''
    main: FrozenMultiset[Card]
    commanders: FrozenMultiset[Card]

    @cached_property
    def cards(self) -> FrozenMultiset[Card]:
        return self.main.union(self.commanders)

    @cached_property
    def identity(self) -> str:
        return merge_color_identities(card.identity for card in self.cards.distinct_elements())

    @cached_property
    def used_commanders(self) -> FrozenMultiset[int]:
        return card_numbers(self.commanders)

    @cached_property
    def used_cards(self) -> FrozenMultiset[int]:
        return card_numbers(self.cards)

    @cached_property
    def templates(self) -> FrozenMultiset[int]:
        '''How many copies of each template the deck holds.

        Both kinds of template are counted the same way, out of the cards each was resolved to: one
        defined by a query is no longer assumed to be present, it is present as many times as the deck
        holds a card that query found.'''
        quantity_by_card_id = [(card.pk, quantity) for card, quantity in self.cards.items()]
        template_id_list = Template.objects \
            .values('id') \
            .annotate(
                quantity_in_deck=Coalesce(
                    Sum(quantity_in_deck('templatematch__card_id', quantity_by_card_id)),
                    0,
                ),
            ) \
            .filter(
                quantity_in_deck__gte=1,
            ) \
            .values_list('id', 'quantity_in_deck')
        return FrozenMultiset[int]({template_id: quantity for template_id, quantity in template_id_list})


def deck_from_raw(raw_deck: RawDeck, cards_by_name: dict[str, Card]) -> Deck:
    main = Multiset[Card]()
    commanders = Multiset[Card]()

    def next_card(raw_card: RawCardInDeck, card_set: Multiset[Card]):
        name = raw_card.card.strip().lower()
        quantity = raw_card.quantity
        if not name or quantity < 1:
            return
        # written as printed first, and then as a keyboard would write it
        card = cards_by_name.get(name) or cards_by_name.get(strip_accents(name))
        if card is not None:
            card_set.add(card, quantity)
    for card in raw_deck.main:
        next_card(card, main)
    for commander in raw_deck.commanders:
        next_card(commander, commanders)
    return Deck(main=FrozenMultiset(main), commanders=FrozenMultiset(commanders))


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

    def deck_cards(self) -> QuerySet[Card]:
        '''The card rows a decklist is resolved against, narrowed to the columns a Deck reads.

        A view that hands the cards themselves back to the caller widens this to the whole row, so that
        serializing them takes no second read of the same rows.'''
        return Card.objects.only('name', 'name_unaccented', 'number', 'identity')

    def parse(self, request: Request) -> Deck:
        data: str | dict = request.data  # type: ignore
        serializer = RawDeckSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        raw_deck: RawDeck = serializer.save()  # type: ignore
        # every card the list names is looked up, not only the ones an editor curated: a card we use in
        # no combo still decides the colours of the deck, and whether it holds something banned
        submitted = {raw_card.card.strip() for raw_card in chain(raw_deck.main, raw_deck.commanders)}
        submitted.discard('')
        names = {name.lower() for name in submitted}
        # a list can name a card by the number it is published under, as well as by its name
        numeric = {int(name) for name in names if name.isdigit()}
        # the same names without their accents and ligatures, so that a list writing Aether Vial finds
        # the card printed with the ligature, and a list writing the ligature finds it back
        plain = {strip_accents(name).lower() for name in names}
        # only the names the list holds are read, never the whole table, and all of them in one query.
        # A name is matched as it is printed, on its own unique index; then by the case the database
        # folds it to; then by the normalized name, which carries no letter outside ASCII and so folds
        # alike on every backend. DeckNameCaseTests spells out what each of the three catches. A branch
        # no name feeds is dropped before the query is compiled, so a list naming no number costs the
        # same as it did when the numbers were read separately.
        cards = (
            self.deck_cards()
            .annotate(lowered=Lower('name'), lowered_plain=Lower('name_unaccented'))
            .filter(Q(name__in=submitted) | Q(lowered__in=names) | Q(lowered_plain__in=plain) | Q(number__in=numeric))
            .order_by()
        )
        cards_by_name: dict[str, Card] = {}
        for card in cards:
            cards_by_name.setdefault(card.name_unaccented.lower(), card)
            cards_by_name[card.name.lower()] = card
            if card.number in numeric:
                cards_by_name[str(card.number)] = card
        return deck_from_raw(raw_deck, cards_by_name)


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
                        F('cardinvariant__quantity') - quantity_in_deck('cardinvariant__card_id', deck.used_cards.items()),
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
