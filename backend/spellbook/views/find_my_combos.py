from drf_spectacular.openapi import AutoSchema
from multiset import FrozenMultiset
from django.db.models import F, Sum, Case, When
from django.db.models.functions import Greatest, Coalesce
from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.pagination import LimitOffsetPagination
from drf_spectacular.utils import extend_schema, Direction
from drf_spectacular.extensions import OpenApiSerializerExtension
from spellbook.models import Variant
from spellbook.models.mixins import PreSerializedSerializer
from spellbook.serializers import VariantSerializer
from website.views import PlainTextDeckListParser
from .variants import VariantViewSet
from .utils import Deck, DecklistAPIView


class FindMyCombosResponseSerializer(serializers.BaseSerializer):
    child = PreSerializedSerializer()
    variant_list_serializer = serializers.ListSerializer(child=child)

    def __new__(cls, *args, **kwargs):
        kwargs['many'] = False
        return super().__new__(cls, *args, **kwargs)

    def to_internal_value(self, data):
        return {
            'variants': self.variant_list_serializer.to_internal_value(data.get('variants', [])),
            'identity': data['identity'],
            'deck': data['deck'],
        }

    def to_representation(self, data):
        identity = data['identity']
        identity_set = set(identity) - {'C'}
        deck: Deck = data['deck']
        cards = deck.main.union(deck.commanders)
        included_variants = []
        included_variants_by_changing_commanders = []
        almost_included_variants = []
        almost_included_variants_by_adding_colors = []
        almost_included_variants_by_changing_commanders = []
        almost_included_variants_by_adding_colors_and_changing_commanders = []
        variants = self.variant_list_serializer.to_representation(data['variants'])
        for variant in variants:
            variant_data: dict = variant
            variant_cards = FrozenMultiset[int]({civ['card']['id']: civ['quantity'] for civ in variant_data['uses']})
            variant_commanders = FrozenMultiset[int]({civ['card']['id']: civ['quantity'] for civ in variant_data['uses'] if civ['must_be_commander']})
            variants_templates = FrozenMultiset[int]({tiv['template']['id']: tiv['quantity'] for tiv in variant_data['requires']})
            variant_identity = set(variant_data['identity']) - {'C'}
            if variant_commanders.issubset(deck.commanders):
                if variant_cards.issubset(cards) and variants_templates.issubset(deck.templates):
                    included_variants.append(variant_data)
                else:
                    if set(variant_identity).issubset(identity_set):
                        almost_included_variants.append(variant_data)
                    else:
                        almost_included_variants_by_adding_colors.append(variant_data)
            elif variant_cards.issubset(cards) and variants_templates.issubset(deck.templates):
                included_variants_by_changing_commanders.append(variant_data)
            else:
                if set(variant_identity).issubset(identity_set):
                    almost_included_variants_by_changing_commanders.append(variant_data)
                else:
                    almost_included_variants_by_adding_colors_and_changing_commanders.append(variant_data)

        return {
            'identity': identity,
            'included': included_variants,
            'included_by_changing_commanders': included_variants_by_changing_commanders,
            'almost_included': almost_included_variants,
            'almost_included_by_adding_colors': almost_included_variants_by_adding_colors,
            'almost_included_by_changing_commanders': almost_included_variants_by_changing_commanders,
            'almost_included_by_adding_colors_and_changing_commanders': almost_included_variants_by_adding_colors_and_changing_commanders,
        }


class FindMyCombosResponseSerializerExtension(OpenApiSerializerExtension):
    target_class = FindMyCombosResponseSerializer

    def get_name(self, auto_schema: AutoSchema, direction: Direction) -> str | None:
        return 'FindMyCombosResponse'

    def map_serializer(self, auto_schema: AutoSchema, direction: Direction) -> dict[str, object]:
        required_properties = {
            'identity': auto_schema._map_serializer_field(serializers.CharField(), direction),
            'included': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'included_by_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_adding_colors': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
            'almost_included_by_adding_colors_and_changing_commanders': auto_schema._map_serializer_field(VariantSerializer(many=True), direction),
        }
        return {
            'type': 'object',
            'properties': required_properties,
            'required': sorted(required_properties),
        }


class FindMyCombosView(DecklistAPIView):
    action = 'list'
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    pagination_class = LimitOffsetPagination
    response = FindMyCombosResponseSerializer
    filter_backends = VariantViewSet.filter_backends
    filterset_class = VariantViewSet.filterset_class

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def get(self, request: Request) -> Response:
        deck = self.parse(request)

        card_quantity_in_deck = Case(
            *(When(cardinvariant__card_id=card_id, then=quantity) for card_id, quantity in deck.cards.items()),
            default=0,
        )

        template_quantity_in_deck = Case(
            *(When(templateinvariant__template_id=template_id, then=quantity) for template_id, quantity in deck.templates.items()),
            default=0,
        )

        variant_id_list = Variant.objects \
            .values('id') \
            .alias(
                missing_count=Coalesce(
                    Sum(
                        Greatest(
                            F('cardinvariant__quantity') - card_quantity_in_deck,
                            0,
                        ),
                    ),
                    0,
                ) + Coalesce(
                    Sum(
                        Greatest(
                            F('templateinvariant__quantity') - template_quantity_in_deck,
                            0,
                        ),
                    ),
                    0,
                ),
            ) \
            .filter(
                missing_count__lte=1,
            )

        viewset = VariantViewSet()
        viewset.setup(self.request)
        variants_query = viewset.filter_queryset(viewset.get_queryset().filter(id__in=variant_id_list))

        paginator = self.pagination_class()
        paginator.max_limit = 1000  # type: ignore
        paginator.default_limit = 1000
        variants_page: list[Variant] = paginator.paginate_queryset(variants_query, request)  # type: ignore
        return paginator.get_paginated_response(FindMyCombosResponseSerializer({
            'variants': variants_page,
            'identity': deck.identity,
            'deck': deck,
        }).data)

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)

    def get_queryset(self):
        # Used by OpenAPI schema generation
        return Variant.objects.none()
