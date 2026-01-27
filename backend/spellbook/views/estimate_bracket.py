from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema
from spellbook.models import Card, Template, Variant, estimate_bracket
from spellbook.serializers import CardSerializer, TemplateSerializer, VariantSerializer, BracketTagSerializer
from website.views import PlainTextDeckListParser
from .utils import DecklistAPIView, find_variants


class ClassifiedVariantSerializer(serializers.Serializer):
    combo = VariantSerializer()
    relevant = serializers.BooleanField()
    borderline_relevant = serializers.BooleanField()
    definitely_two_card = serializers.BooleanField()
    speed = serializers.IntegerField()


class EstimateBracketResultSerializer(serializers.Serializer):
    bracket_tag = BracketTagSerializer()
    game_changer_cards = serializers.ListField(child=CardSerializer(), source='data.game_changer_cards')
    mass_land_denial_cards = serializers.ListField(child=CardSerializer(), source='data.mass_land_denial_cards')
    mass_land_denial_templates = serializers.ListField(child=TemplateSerializer(), source='data.mass_land_denial_templates')
    mass_land_denial_combos = serializers.ListField(child=VariantSerializer(), source='data.mass_land_denial_combos')
    extra_turn_cards = serializers.ListField(child=CardSerializer(), source='data.extra_turn_cards')
    extra_turn_templates = serializers.ListField(child=TemplateSerializer(), source='data.extra_turn_templates')
    extra_turns_combos = serializers.ListField(child=VariantSerializer(), source='data.extra_turns_combos')
    lock_combos = serializers.ListField(child=VariantSerializer(), source='data.lock_combos')
    control_all_opponents_combos = serializers.ListField(child=VariantSerializer(), source='data.control_all_opponents_combos')
    control_some_opponents_combos = serializers.ListField(child=VariantSerializer(), source='data.control_some_opponents_combos')
    skip_turns_combos = serializers.ListField(child=VariantSerializer(), source='data.skip_turns_combos')
    two_card_combos = serializers.ListField(child=ClassifiedVariantSerializer(), source='data.two_card_combos')


class EstimateBracketView(DecklistAPIView):
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    response = EstimateBracketResultSerializer

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def get(self, request: Request) -> Response:
        deck = self.parse(request)

        cards = list(
            Card
            .objects
            .filter(pk__in=deck.cards.distinct_elements())
        )
        templates = list(
            Template
            .objects
            .filter(pk__in=deck.templates.distinct_elements())
            .exclude(scryfall_query__isnull=False)
        )

        variant_id_list = find_variants(deck, missing=0)
        variants_query = Variant.recipes_prefetched \
            .filter(status__in=Variant.public_statuses()) \
            .filter(id__in=variant_id_list)
        variants = list(variants_query)

        result = estimate_bracket(cards, templates, tuple((v, v.get_recipe()) for v in variants))
        serializer = self.response(result)
        return Response(serializer.data)

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
