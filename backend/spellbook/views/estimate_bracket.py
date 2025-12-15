from rest_framework import parsers, serializers
from rest_framework.response import Response
from rest_framework.request import Request
from drf_spectacular.utils import extend_schema
from spellbook.models import Card, Template, estimate_bracket
from spellbook.serializers import CardSerializer, TemplateSerializer, VariantSerializer, BracketTagSerializer
from spellbook.views import FindMyCombosView
from website.views import PlainTextDeckListParser
from .utils import DecklistAPIView


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
    skip_turns_combos = serializers.ListField(child=VariantSerializer(), source='data.skip_turns_combos')
    definitely_early_game_two_card_combos = serializers.ListField(child=VariantSerializer(), source='data.definitely_early_game_two_card_combos')
    arguably_early_game_two_card_combos = serializers.ListField(child=VariantSerializer(), source='data.arguably_early_game_two_card_combos')
    definitely_late_game_two_card_combos = serializers.ListField(child=VariantSerializer(), source='data.definitely_late_game_two_card_combos')
    borderline_late_game_two_card_combos = serializers.ListField(child=VariantSerializer(), source='data.borderline_late_game_two_card_combos')


class EstimateBracketView(DecklistAPIView):
    permission_classes = []
    parser_classes = [PlainTextDeckListParser, parsers.JSONParser]
    response = EstimateBracketResultSerializer

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def get(self, request: Request) -> Response:
        deck = self.parse(request)

        cards = list(Card.objects.filter(pk__in=deck.cards.distinct_elements()))
        templates = list(Template.objects.filter(replacements__in=cards).distinct())

        find_my_combos_view = FindMyCombosView()
        find_my_combos_view.setup(request)  # type: ignore
        variants_query = find_my_combos_view.find_variants(deck)
        variants = list(variants_query)

        result = estimate_bracket(cards, templates, tuple((v, v.get_recipe()) for v in variants))
        serializer = self.response(result)
        return Response(serializer.data)

    @extend_schema(request=DecklistAPIView.request, responses=response)
    def post(self, request: Request) -> Response:
        return self.get(request)
