from collections import defaultdict
from rest_framework import viewsets, parsers
from rest_framework.decorators import api_view, parser_classes
from rest_framework.response import Response
from rest_framework.request import Request
from spellbook.models import Card, Template, Feature, Combo, Variant, CardInVariant
from spellbook.variants.list_utils import merge_identities
from spellbook.serializers import CardDetailSerializer, FeatureSerializer, ComboDetailSerializer, TemplateSerializer, VariantSerializer


class VariantViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Variant.objects.filter(status=Variant.Status.OK).prefetch_related(
        'cardinvariant_set__card',
        'templateinvariant_set__template',
        'cardinvariant_set',
        'templateinvariant_set',
        'produces',
        'of',
        'includes')
    serializer_class = VariantSerializer


class FeatureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Feature.objects.all()
    serializer_class = FeatureSerializer


class ComboViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Combo.objects.prefetch_related(
        'cardincombo_set__card',
        'templateincombo_set__template',
        'cardincombo_set',
        'templateincombo_set',
        'produces',
        'needs')
    serializer_class = ComboDetailSerializer


class CardViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Card.objects.prefetch_related(
        'features',
    )
    serializer_class = CardDetailSerializer


class TemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Template.objects.all()
    serializer_class = TemplateSerializer


class DeckListParser(parsers.BaseParser):
    media_type = 'text/plain'

    def __init__(self):
        self.cards_dict = {c.name.lower(): c for c in Card.objects.all()}

    def parse(self, stream, media_type=None, parser_context=None):
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', 'UTF-8')
        lines = stream.read().decode(encoding).splitlines()
        result = set[Card]()
        for line in lines[:500]:
            line = line.strip().lower()
            if line and line in self.cards_dict:
                result.add(self.cards_dict[line])
        return result


@api_view()
@parser_classes([DeckListParser])
def find_my_combos(request: Request) -> Response:
    cards: set[Card] = request.data
    variant_to_cards = defaultdict[Variant, set[Card]](set)
    for civ in CardInVariant.objects \
        .filter(variant__status=Variant.Status.OK, variant__uses__in=cards) \
        .prefetch_related(
            'card',
            'variant'):
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
