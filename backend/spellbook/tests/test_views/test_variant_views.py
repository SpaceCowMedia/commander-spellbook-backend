import json
import random
from unittest.mock import patch
from django.db import models
from django.urls import reverse
from rest_framework import status
from constants import SORTED_COLORS
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Template, Feature, Variant, CardInVariant, TemplateInVariant, Combo, VariantAlias
from spellbook.views import VariantViewSet
from spellbook.serializers import VariantSerializer
from spellbook.transformers.variants_query_transformer import variants_query_parser
from spellbook.views.variants import VariantGroupedByComboFilter
from website.models import WebsiteProperty, FEATURED_SET_CODES_PROPERTIES
from ..testing import SpellbookTestCaseWithSeeding


class VariantViewsTests(SpellbookTestCaseWithSeeding):
    public_variants: models.Manager[Variant]
    ok_variants: models.QuerySet[Variant]
    operators = {
        '>': 'gt',
        '<': 'lt',
        '>=': 'gte',
        '<=': 'lte',
        '=': 'exact',
        ':': 'exact',
    }

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        super().generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        Variant.objects.filter(
            id__in=Variant.objects
            .exclude(uses__name__icontains='b')
            .values_list('id', flat=True),
        ).update(status=Variant.Status.EXAMPLE)
        cls.v1_id: int = Variant.objects.first().id  # type: ignore
        cls.public_variants: models.Manager[Variant] = VariantViewSet.queryset
        cls.ok_variants = cls.public_variants.filter(status=Variant.Status.OK)
        cls.update_variants()
        cls.bulk_serialize_variants()

    def variant_assertions(self, variant_result):
        v: Variant = Variant.objects.get(id=variant_result.id)
        self.assertEqual(variant_result.id, v.id)
        self.assertEqual(variant_result.status, v.status)
        self.assertEqual(variant_result.identity, v.identity)
        self.assertEqual(variant_result.popularity, v.popularity)
        if v.status == Variant.Status.EXAMPLE:
            self.assertEqual(variant_result.mana_needed, None)
            self.assertEqual(variant_result.easy_prerequisites, None)
            self.assertEqual(variant_result.notable_prerequisites, None)
            self.assertEqual(variant_result.description, None)
            self.assertEqual(variant_result.notes, None)
        else:
            self.assertEqual(variant_result.mana_needed, v.mana_needed)
            self.assertEqual(variant_result.notable_prerequisites, v.notable_prerequisites)
            self.assertEqual(variant_result.description, v.description)
            self.assertEqual(variant_result.notes, v.notes)
        self.assertEqual(variant_result.legalities.commander, v.legal_commander)
        self.assertEqual(variant_result.legalities.pauper_commander_main, v.legal_pauper_commander_main)
        self.assertEqual(variant_result.legalities.pauper_commander, v.legal_pauper_commander)
        self.assertEqual(variant_result.legalities.oathbreaker, v.legal_oathbreaker)
        self.assertEqual(variant_result.legalities.predh, v.legal_predh)
        self.assertEqual(variant_result.legalities.standard_brawl, v.legal_standard_brawl)
        self.assertEqual(variant_result.legalities.brawl, v.legal_brawl)
        self.assertEqual(variant_result.legalities.competitive_brawl, v.legal_competitive_brawl)
        self.assertEqual(variant_result.legalities.alchemy, v.legal_alchemy)
        self.assertEqual(variant_result.legalities.vintage, v.legal_vintage)
        self.assertEqual(variant_result.legalities.legacy, v.legal_legacy)
        self.assertEqual(variant_result.legalities.premodern, v.legal_premodern)
        self.assertEqual(variant_result.legalities.modern, v.legal_modern)
        self.assertEqual(variant_result.legalities.pioneer, v.legal_pioneer)
        self.assertEqual(variant_result.legalities.standard, v.legal_standard)
        self.assertEqual(variant_result.legalities.pauper, v.legal_pauper)
        self.assertEqual(variant_result.prices.tcgplayer, str(v.price_tcgplayer))
        self.assertEqual(variant_result.prices.cardkingdom, str(v.price_cardkingdom))
        self.assertEqual(variant_result.prices.cardmarket, str(v.price_cardmarket))
        self.assertEqual(variant_result.spoiler, v.spoiler)
        uses_list = [u.id for u in v.uses.all()]
        for u in variant_result.uses:
            card = u.card
            self.assertIn(card.id, uses_list)
            c = Card.objects.get(id=card.id)
            self.assertEqual(card.id, c.id)
            self.assertEqual(card.name, c.name)
            self.assertEqual(card.oracle_id, str(c.oracle_id))
            self.assertEqual(card.spoiler, c.spoiler)
            self.assertEqual(card.type_line, c.type_line)
            self.assertEqual(card.image_uri_front_png, c.image_uri_front_png)
            self.assertEqual(card.image_uri_front_large, c.image_uri_front_large)
            self.assertEqual(card.image_uri_front_normal, c.image_uri_front_normal)
            self.assertEqual(card.image_uri_front_small, c.image_uri_front_small)
            self.assertEqual(card.image_uri_front_art_crop, c.image_uri_front_art_crop)
            self.assertEqual(card.layout_rotation_front, c.layout_rotation_front)
            self.assertEqual(card.image_uri_back_png, c.image_uri_back_png)
            self.assertEqual(card.image_uri_back_large, c.image_uri_back_large)
            self.assertEqual(card.image_uri_back_normal, c.image_uri_back_normal)
            self.assertEqual(card.image_uri_back_small, c.image_uri_back_small)
            self.assertEqual(card.image_uri_back_art_crop, c.image_uri_back_art_crop)
            vic = CardInVariant.objects.get(variant=v.id, card=c)
            self.assertEqual(set(u.zone_locations), set(vic.zone_locations))
            self.assertEqual(u.must_be_commander, vic.must_be_commander)
            self.assertEqual(u.quantity, vic.quantity)
            if v.status == Variant.Status.EXAMPLE:
                self.assertEqual(u.battlefield_card_state, None)
                self.assertEqual(u.exile_card_state, None)
                self.assertEqual(u.library_card_state, None)
                self.assertEqual(u.graveyard_card_state, None)
            else:
                self.assertEqual(u.battlefield_card_state, vic.battlefield_card_state)
                self.assertEqual(u.exile_card_state, vic.exile_card_state)
                self.assertEqual(u.library_card_state, vic.library_card_state)
                self.assertEqual(u.graveyard_card_state, vic.graveyard_card_state)
        requires_list = [r.id for r in v.requires.all()]
        for r in variant_result.requires:
            template = r.template
            self.assertIn(template.id, requires_list)
            t = Template.objects.get(id=template.id)
            self.assertEqual(template.id, t.id)
            self.assertEqual(template.name, t.name)
            self.assertEqual(template.scryfall_query, t.scryfall_query)
            self.assertEqual(template.scryfall_api, t.scryfall_api())
            tiv = TemplateInVariant.objects.get(variant=v.id, template=t)
            self.assertEqual(set(r.zone_locations), set(tiv.zone_locations))
            self.assertEqual(r.must_be_commander, tiv.must_be_commander)
            self.assertEqual(r.quantity, tiv.quantity)
            if v.status == Variant.Status.EXAMPLE:
                self.assertEqual(r.battlefield_card_state, None)
                self.assertEqual(r.exile_card_state, None)
                self.assertEqual(r.library_card_state, None)
                self.assertEqual(r.graveyard_card_state, None)
            else:
                self.assertEqual(r.battlefield_card_state, tiv.battlefield_card_state)
                self.assertEqual(r.exile_card_state, tiv.exile_card_state)
                self.assertEqual(r.library_card_state, tiv.library_card_state)
                self.assertEqual(r.graveyard_card_state, tiv.graveyard_card_state)
        produces_list = [p.id for p in v.produces.all()]
        for p in variant_result.produces:
            self.assertIn(p.feature.id, produces_list)
            f = Feature.objects.get(id=p.feature.id)
            self.assertEqual(p.feature.id, f.id)
            self.assertEqual(p.feature.name, f.name)
            self.assertEqual(p.feature.uncountable, f.uncountable)
        of_list = [o.id for o in v.of.all()]
        for o in variant_result.of:
            self.assertIn(o.id, of_list)
        includes_list = [i.id for i in v.includes.all()]
        for i in variant_result.includes:
            self.assertIn(i.id, includes_list)
        self.assertEqual(variant_result.variant_count, self.public_variants.filter(of__variants=v.id).values('id').distinct().count())

    def test_variants_list_view(self):
        response = self.client.get(reverse('variants-list'), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        variant_count = self.public_variants.count()
        self.assertEqual(len(result.results), variant_count)
        for i in range(variant_count):
            self.variant_assertions(result.results[i])

    def test_variants_detail_view(self):
        response = self.client.get(reverse('variants-detail', args=[self.v1_id]), follow=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.v1_id)
        self.variant_assertions(result)

    def variants_matching_all_cards(self, matching_cards: models.QuerySet[Card]) -> models.QuerySet[Variant]:
        variants_with_only_matching_cards = self.public_variants.exclude(uses__in=Card.objects.exclude(pk__in=matching_cards)).order_by()
        return variants_with_only_matching_cards.distinct()
        # templates_without_matching_cards = Template.objects.exclude(replacements__isnull=True).exclude(replacements__in=matching_cards).order_by()
        # variants_with_only_matching_cards_without_templates_without_matching_cards = variants_with_only_matching_cards.exclude(requires__in=templates_without_matching_cards)
        # variants = variants_with_only_matching_cards_without_templates_without_matching_cards.distinct()
        # return variants

    def variants_matching_any_cards(self, matching_cards: models.QuerySet[Card]) -> models.QuerySet[Variant]:
        variants_with_matching_cards = self.public_variants.filter(uses__in=matching_cards)
        return variants_with_matching_cards.distinct()
        # variants_with_matching_templates = self.public_variants.filter(requires__replacements__in=matching_cards)
        # variants = self.public_variants.filter(pk__in=variants_with_matching_cards.values('pk').order_by().union(variants_with_matching_templates.values('pk').order_by())).distinct()
        # return variants

    def test_variants_list_view_query_by_card_name(self):
        a_card = Card.objects.get(pk=self.c1_id)
        queries: list[tuple[str, str]] = []
        for search in (name for c in Card.objects.all() for name in (c.name, c.name_unaccented, c.name_unaccented.replace('-', ''), c.name_unaccented.replace('-', ' '))):
            prefix_without_spaces = search.partition(' ')[0]
            search_without_underscores = search.replace('_', '').strip()
            search_with_simplified_underscores = search.replace('_____', '_')
            queries += [
                (prefix_without_spaces, prefix_without_spaces),
                (f'"{prefix_without_spaces}"', prefix_without_spaces),
                (f'"{search}"', search),
                (f'"{search_without_underscores}"', search_without_underscores),
                (f'"{search_with_simplified_underscores}"', search_with_simplified_underscores),
                (f'card:{prefix_without_spaces}', prefix_without_spaces),
                (f'card:"{prefix_without_spaces}"', prefix_without_spaces),
                (f'card:"{search}"', search),
                (f'card="{search}"', search),
                (f'@card:{prefix_without_spaces}', prefix_without_spaces),
                (f'@card:"{prefix_without_spaces}"', prefix_without_spaces),
            ]
        queries = list(dict.fromkeys(queries))
        # case insensitive queries: isascii() is used to filter out case insensitive accented queries, incompatible with sqlite:
        # https://docs.djangoproject.com/en/5.0/ref/databases/#substring-matching-and-case-sensitivity
        queries += [
            (q.upper(), term) for q, term in queries if not q.isupper() and q.isascii()
        ] + [
            (q.lower(), term) for q, term in queries if not q.islower() and q.isascii()
        ]
        queries += [
            ('@card:" "', ' '),
        ]
        queries = list(dict.fromkeys(queries))
        for q, term in queries:
            if '=' in q:
                matching_cards = Card.objects.filter(
                    models.Q(name__iexact=term) | models.Q(name_unaccented__iexact=term) | models.Q(name_unaccented_simplified__iexact=term) | models.Q(name_unaccented_simplified_with_spaces__iexact=term)
                )
            else:
                matching_cards = Card.objects.filter(
                    models.Q(name__icontains=term) | models.Q(name_unaccented__icontains=term) | models.Q(name_unaccented_simplified__icontains=term) | models.Q(name_unaccented_simplified_with_spaces__icontains=term)
                )
            if '@' in q:
                variants = self.variants_matching_all_cards(matching_cards)
            else:
                variants = self.variants_matching_any_cards(matching_cards)
            with self.subTest(f'query by card name: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)
            qq = f'{q} card:"{a_card.name}"'
            with self.subTest(f'query by card name: {term} with additional card {a_card} and query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': qq}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = variants.filter(uses__id=a_card.id).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_template_name(self):
        queries: list[tuple[str, str]] = []
        for search in (t.name for t in Template.objects.all()):
            prefix_without_spaces = search.partition(' ')[0]
            queries += [
                (f'template:{prefix_without_spaces}', prefix_without_spaces),
                (f'template:"{search}"', search),
                (f'template="{search}"', search),
            ]
        queries = list(dict.fromkeys(queries))
        queries += [
            (q.upper(), term) for q, term in queries if not q.isupper() and q.isascii()
        ] + [
            (q.lower(), term) for q, term in queries if not q.islower() and q.isascii()
        ]
        queries += [
            ('@template:" "', ' '),
        ]
        queries = list(dict.fromkeys(queries))
        for q, term in queries:
            if '=' in q:
                matching_templates = Template.objects.filter(
                    models.Q(name__iexact=term)
                )
            else:
                matching_templates = Template.objects.filter(
                    models.Q(name__icontains=term)
                )
            if '@' in q:
                variants = self.public_variants.exclude(requires__in=Template.objects.exclude(pk__in=matching_templates)).distinct()
            else:
                variants = self.public_variants.filter(requires__in=matching_templates).distinct()
            with self.subTest(f'query by template name: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_card_count(self):
        min_cards, max_cards = self.public_variants.aggregate(min_cards=models.Min('card_count'), max_cards=models.Max('card_count')).values()
        self.assertGreaterEqual(max_cards, min_cards)
        for card_count in (min_cards, max_cards, (min_cards + max_cards) // 2):
            for o, o_django in self.operators.items():
                q = f'cards{o}{card_count}'
                q_django = {f'card_count__{o_django}': card_count}
                with self.subTest(f'query by card count: {card_count} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants = self.public_variants.filter(**q_django).distinct()
                    self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                    for v in result.results:
                        self.variant_assertions(v)
        with self.subTest('Test all- prefix with card_count'):
            response = self.client.get(reverse('variants-list'), query_params={'q': f'all-cards:{2}'}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        with self.subTest('Test invalid quotes with card count'):
            response = self.client.get(reverse('variants-list'), query_params={'q': f'cards:"{2}"'}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            self.assertEqual(len(result.results), 0)

    def test_variants_list_view_query_by_template_count(self):
        min_templates, max_templates = self.public_variants.aggregate(min_templates=models.Min('template_count'), max_templates=models.Max('template_count')).values()
        self.assertGreaterEqual(max_templates, min_templates)
        for template_count in (min_templates, max_templates, (min_templates + max_templates) // 2):
            for o, o_django in self.operators.items():
                q = f'templates{o}{template_count}'
                q_django = {f'template_count__{o_django}': template_count}
                with self.subTest(f'query by template count: {template_count} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants = self.public_variants.filter(**q_django).distinct()
                    self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                    for v in result.results:
                        self.variant_assertions(v)
        with self.subTest('Test all- prefix in combination with template_count'):
            response = self.client.get(reverse('variants-list'), query_params={'q': f'all-templates:{2}'}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_variants_list_view_query_by_card_type(self):
        queries: list[tuple[str, str]] = []
        for card_type in ('instant', 'creature'):
            queries += [
                (f'cardtype:{card_type}', card_type),
                (f'type:{card_type[:-3]}', card_type),
                (f'type:"{card_type[:-3]}"', card_type),
                (f'type:{card_type}', card_type),
                (f'type="{card_type}"', card_type),
            ]
        queries += [
            ('@type:"a"', 'a'),
        ]
        for (q, term) in queries:
            if '=' in q:
                matching_cards = Card.objects.filter(
                    models.Q(type_line__iexact=term)
                )
            else:
                matching_cards = Card.objects.filter(
                    models.Q(type_line__icontains=term)
                )
            if '@' in q:
                variants = self.variants_matching_all_cards(matching_cards)
            else:
                variants = self.variants_matching_any_cards(matching_cards)
            with self.subTest(f'query by card type: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_card_oracle_text(self):
        queries: list[tuple[str, str]] = []
        for i in range(10):
            queries += [
                (f'cardoracle:"x{i}"', f'x{i}'),
                (f'oracle:"x{i}"', f'x{i}'),
                (f'o:x{i}', f'x{i}'),
                (f'text:x{i}', f'x{i}'),
                (f'oracle="x{i}"', f'x{i}'),
                (f'o=x{i}', f'x{i}'),
            ]
        queries += [
            ('@oracle:"x"', 'x'),
        ]
        for (q, term) in queries:
            if '=' in q:
                matching_cards = Card.objects.filter(
                    models.Q(oracle_text__iexact=term)
                )
            else:
                matching_cards = Card.objects.filter(
                    models.Q(oracle_text__icontains=term)
                )
            if '@' in q:
                variants = self.variants_matching_all_cards(matching_cards)
            else:
                variants = self.variants_matching_any_cards(matching_cards)
            with self.subTest(f'query by card oracle text: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_card_keywords(self):
        queries: list[tuple[str, str]] = []
        for keyword in {k for v in Variant.objects.values_list('uses__keywords', flat=True) for k in v}:
            queries += [
                (f'cardkeywords:{keyword}', keyword),
                (f'cardkeyword:{keyword}', keyword),
                (f'keyword:{keyword}', keyword),
                (f'keywords:"{keyword}"', keyword),
                (f'keyword:{keyword}', keyword),
            ]
        queries += [
            ('@keyword:"k"', 'k'),
        ]
        for (q, term) in queries:
            matching_cards = Card.objects.filter(
                models.Q(keywords__icontains=term)
            )
            if '@' in q:
                variants = self.variants_matching_all_cards(matching_cards)
            else:
                variants = self.variants_matching_any_cards(matching_cards)
            with self.subTest(f'query by card keyword: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_card_mana_value(self):
        queries: list[tuple[str, str, int]] = []
        for operator, operator_django in self.operators.items():
            for mv in range(10):
                queries += [
                    (f'cardmanavalue{operator}{mv}', operator_django, mv),
                    (f'manavalue{operator}{mv}', operator_django, mv),
                    (f'mv{operator}{mv}', operator_django, mv),
                    (f'cmc{operator}{mv}', operator_django, mv),
                    (f'@mv{operator}{mv}', operator_django, mv),
                ]
        for (q, operator_django, mv) in queries:
            q_django = {f'mana_value__{operator_django}': mv}
            matching_cards = Card.objects.filter(**q_django)
            if '@' in q:
                variants = self.variants_matching_all_cards(matching_cards)
            else:
                variants = self.variants_matching_any_cards(matching_cards)
            with self.subTest(f'query by card mana value: {mv} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_cardcolor(self):
        for operator, operator_django in self.operators.items():
            queries = []
            for color in SORTED_COLORS:
                color = list(color)
                random.shuffle(color)
                color = ''.join(color)
                if not color:
                    raise ValueError('Empty color')
                queries.extend([
                    (f'cardcolor{operator}{color}', color),
                    (f'cardcolors{operator}{color}', color),
                    (f'@cardcolor{operator}{color}', color),
                ])
            for color_name, color in [('blue', 'U'), ('black', 'B'), ('COLORLESS', 'C')]:
                queries.extend([
                    (f'cardcolor{operator}{color_name}', color),
                    (f'cardcolors{operator}"{color_name}"', color),
                ])
            for i in range(7):
                queries.extend([
                    (f'cardcolor{operator}{i}', i),
                    (f'cardcolors{operator}{i}', i),
                    (f'@cardcolor{operator}{i}', i),
                ])
            for q, color in queries:
                with self.subTest(f'query by card color: {color} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    if isinstance(color, int):
                        qq = {f'color_count__{operator_django}': color}
                        if '@' in q:
                            variants = self.variants_matching_all_cards(Card.objects.filter(**qq))
                        else:
                            variants = self.variants_matching_any_cards(Card.objects.filter(**qq))
                    elif isinstance(color, str):
                        color_set = set(color) - {'C'}
                        qq = {f'color_count__{operator_django}': len(color_set)}
                        if '@' in q:
                            variants_result = self.variants_matching_all_cards(Card.objects.filter(**qq))
                        else:
                            variants_result = self.variants_matching_any_cards(Card.objects.filter(**qq))
                        variants = []
                        for v in variants_result:
                            ok = '@' in q
                            for c in v.uses.all():
                                c: Card
                                c_set = set(c.color) - {'C'}
                                if c_set == color_set and '=' in operator or \
                                    c_set.issuperset(color_set) and c_set != color_set and '>' in operator or \
                                        c_set.issubset(color_set) and c_set != color_set and '<' in operator or \
                                        c_set == color_set and ':' in operator:
                                    if '@' not in q:
                                        ok = True
                                        break
                                else:
                                    if '@' in q:
                                        ok = False
                                        break
                            if ok:
                                variants.append(v)
                    query_result_ids = {v.id for v in result.results}
                    variants_ids = {v.id for v in variants}
                    self.assertSetEqual(query_result_ids, variants_ids)
                    for v in result.results:
                        self.variant_assertions(v)

    def test_variants_list_view_query_by_identity(self):
        for operator, operator_django in self.operators.items():
            queries = []
            for identity in SORTED_COLORS:
                identity = list(identity)
                random.shuffle(identity)
                identity = ''.join(identity)
                if not identity:
                    raise ValueError('Empty identity')
                queries.extend([
                    (f'coloridentity{operator}{identity}', identity),
                    (f'identity{operator}{identity}', identity),
                    (f'color{operator}{identity}', identity),
                    (f'colors{operator}{identity}', identity),
                    (f'id{operator}{identity}', identity),
                    (f'ids{operator}{identity}', identity),
                    (f'c{operator}{identity}', identity),
                    (f'ci{operator}{identity}', identity),
                ])
            for identity_name, identity in [('simic', 'UG'), ('Golgari', 'BG'), ('COLORLESS', 'C')]:
                queries.extend([
                    (f'coloridentity{operator}{identity_name}', identity),
                    (f'identity{operator}"{identity_name}"', identity),
                ])
            for i in range(7):
                queries.extend([
                    (f'coloridentity{operator}{i}', i),
                    (f'identity{operator}{i}', i),
                    (f'color{operator}{i}', i),
                    (f'colors{operator}{i}', i),
                    (f'id{operator}{i}', i),
                    (f'ids{operator}{i}', i),
                    (f'c{operator}{i}', i),
                    (f'ci{operator}{i}', i),
                ])
            for q, identity in queries:
                with self.subTest(f'query by identity: {identity} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    if isinstance(identity, int):
                        qq = {f'identity_count__{operator_django}': identity}
                        variants = self.public_variants.filter(**qq).distinct()
                    elif isinstance(identity, str):
                        identity_set = set(identity) - {'C'}
                        operator_for_query = operator_django if operator != ':' else 'lte'
                        qq = {f'identity_count__{operator_for_query}': len(identity_set)}
                        variants_result = self.public_variants.filter(**qq).distinct()
                        variants = []
                        for v in variants_result:
                            id_set = set(v.identity)
                            if id_set == identity_set and '=' in operator or \
                                id_set.issuperset(identity_set) and id_set != identity_set and '>' in operator or \
                                    id_set.issubset(identity_set) and id_set != identity_set and '<' in operator or \
                                    id_set.issubset(identity_set) and ':' in operator:
                                variants.append(v)
                    query_result_ids = {v.id for v in result.results}
                    variants_ids = {v.id for v in variants}
                    self.assertSetEqual(query_result_ids, variants_ids)
                    for v in result.results:
                        self.variant_assertions(v)

    def test_variants_list_view_query_by_prerequisites(self):
        for operator, operator_django in self.operators.items():
            for i in range(3):
                queries = [
                    f'prerequisites{operator}{i}',
                    f'prerequisite{operator}{i}',
                    f'prereq{operator}{i}',
                    f'pre{operator}{i}',
                ]
                for q in queries:
                    q_django = {f'prerequisites_line_count__{operator_django}': i}
                    with self.subTest(f'query by prerequisites: {i} with query {q}'):
                        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        self.assertEqual(response.get('Content-Type'), 'application/json')
                        result = json.loads(response.content, object_hook=json_to_python_lambda)
                        variants = self.ok_variants.filter(**q_django).distinct()
                        self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                        for v in result.results:
                            self.variant_assertions(v)
        c = Combo.objects.first()
        prereq = (c.notable_prerequisites + '\n' + c.easy_prerequisites).split(maxsplit=2)[0]  # type: ignore
        queries = [
            f'prerequisites:"{prereq}"',
            f'prerequisite:{prereq}',
            f'prereq:{prereq}',
            f'pre:{prereq}',
        ]
        for q in queries:
            with self.subTest(f'query by prerequisites: {prereq} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = self.ok_variants.filter(models.Q(easy_prerequisites__icontains=prereq) | models.Q(notable_prerequisites__icontains=prereq)).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)
        c = Combo.objects.first()
        assert c is not None
        prereq = c.easy_prerequisites or c.notable_prerequisites
        queries = [
            f'prerequisite="{prereq}"',
            f'prerequisites="{prereq}"',
        ]
        for q in queries:
            with self.subTest(f'query by prerequisites: {prereq} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = self.ok_variants.filter(models.Q(easy_prerequisites__iexact=prereq) | models.Q(notable_prerequisites__iexact=prereq)).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_steps(self):
        for operator, operator_django in self.operators.items():
            for i in range(3):
                queries = [
                    f'steps{operator}{i}',
                    f'step{operator}{i}',
                    f'description{operator}{i}',
                    f'desc{operator}{i}',
                ]
                for q in queries:
                    q_django = {f'description_line_count__{operator_django}': i}
                    with self.subTest(f'query by steps: {i} with query {q}'):
                        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        self.assertEqual(response.get('Content-Type'), 'application/json')
                        result = json.loads(response.content, object_hook=json_to_python_lambda)
                        variants = self.ok_variants.filter(**q_django).distinct()
                        self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                        for v in result.results:
                            self.variant_assertions(v)
        steps = Combo.objects.first().description.split(maxsplit=2)[0]  # type: ignore
        queries = [
            f'steps:"{steps}"',
            f'step:{steps}',
            f'description:{steps}',
            f'desc:{steps}',
        ]
        for q in queries:
            with self.subTest(f'query by steps: {steps} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = self.ok_variants.filter(description__icontains=steps).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)
        steps = Combo.objects.first().description  # type: ignore
        queries = [
            f'step="{steps}"',
            f'steps="{steps}"',
        ]
        for q in queries:
            with self.subTest(f'query by steps: {steps} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = self.ok_variants.filter(description__iexact=steps).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_results(self):
        min_results, max_results = self.public_variants.aggregate(min_results=models.Min('result_count'), max_results=models.Max('result_count')).values()
        self.assertGreaterEqual(max_results, min_results)
        for result_count in (min_results, max_results, (min_results + max_results) // 2):
            for o, o_django in self.operators.items():
                queries = [
                    f'results{o}{result_count}',
                    f'result{o}{result_count}',
                ]
                for q in queries:
                    q_django = {f'result_count__{o_django}': result_count}
                    with self.subTest(f'query by results count: {result_count} with query {q}'):
                        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        self.assertEqual(response.get('Content-Type'), 'application/json')
                        result = json.loads(response.content, object_hook=json_to_python_lambda)
                        variants = self.public_variants.filter(**q_django).distinct()
                        self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                        for v in result.results:
                            self.variant_assertions(v)
        text_queries: list[tuple[str, str]] = []
        for feature in Feature.objects.exclude(status__in=(Feature.Status.HIDDEN_UTILITY, Feature.Status.PUBLIC_UTILITY)):
            name_without_spaces = feature.name.split()[0]
            text_queries += [
                (f'results:"{feature.name}"', feature.name),
                (f'results="{feature.name}"', feature.name),
                (f'results:{name_without_spaces}', name_without_spaces),
            ]
        text_queries += [
            ('@results:"a"', ' '),
        ]
        for (q, term) in text_queries:
            if '=' in q:
                matching_features = Feature.objects.filter(
                    models.Q(name__iexact=term)
                )
            else:
                matching_features = Feature.objects.filter(
                    models.Q(name__icontains=term)
                )
            if '@' in q:
                variants = self.public_variants.exclude(produces__in=Feature.objects.exclude(pk__in=matching_features)).distinct()
            else:
                variants = self.public_variants.filter(produces__in=matching_features).distinct()
            with self.subTest(f'query by results: {term} with query {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)

    def test_variants_list_view_query_by_tag(self):
        for preview_tag in (
            'preview',
            'previewed',
            'spoiler',
            'spoiled',
        ):
            query = f'is:{preview_tag}'
            with self.subTest(f'query by tag: {preview_tag} with query {query}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                variants = self.public_variants.filter(spoiler=True).distinct()
                self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                for v in result.results:
                    self.variant_assertions(v)
        query = 'is:commander'
        with self.subTest(f'query by tag: commander with query {query}'):
            response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            variants = self.public_variants.filter(cardinvariant__must_be_commander=True).distinct()
            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
            for v in result.results:
                self.variant_assertions(v)
        c1: Card = Card.objects.all()[0]  # type: ignore
        c1.reserved = True
        c1.save()
        for v in Variant.objects.all():
            v.update_serialized(VariantSerializer)
            v.save()
        query = 'is:reserved'
        with self.subTest(f'query by tag: reserved with query {query}'):
            response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            variants = self.public_variants.filter(uses__reserved=True).distinct()
            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
            for v in result.results:
                self.variant_assertions(v)
        WebsiteProperty.objects.filter(key=FEATURED_SET_CODES_PROPERTIES[0]).update(value='STX,DND')
        WebsiteProperty.objects.filter(key=FEATURED_SET_CODES_PROPERTIES[1]).update(value='ALPHA')
        c1: Card = Card.objects.all()[0]  # type: ignore
        c1.reprinted = False
        c1.latest_printing_set = 'stx'
        c1.save()
        c2: Card = Card.objects.all()[1]  # type: ignore
        c2.reprinted = False
        c2.latest_printing_set = 'dnd'
        c2.save()
        c3: Card = Card.objects.all()[2]  # type: ignore
        c3.reprinted = True
        c3.latest_printing_set = 'alpha'
        c3.save()
        query = 'is:featured'
        with self.subTest(f'query by tag: featured with query {query}'):
            response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            variants = self.public_variants.filter(uses__latest_printing_set__in=['stx', 'dnd', 'alpha'], uses__reprinted=False).distinct()
            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
            for v in result.results:
                self.variant_assertions(v)
        query = 'is:featured-2'
        with self.subTest(f'query by tag: featured in tab 2 with query {query}'):
            response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            variants = self.public_variants.filter(uses__latest_printing_set__in=['alpha'], uses__reprinted=False).distinct()
            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
            for v in result.results:
                self.variant_assertions(v)
        query = 'is:complete'
        with self.subTest(f'query by tag: complete with query {query}'):
            response = self.client.get(reverse('variants-list'), query_params={'q': query}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            variants = self.public_variants.filter(produces__status=Feature.Status.STANDALONE).distinct()
            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
            for v in result.results:
                self.variant_assertions(v)

    def test_variants_list_view_query_by_spellbook_id(self):
        for variant in Variant.objects.all()[:3]:
            queries = [
                f'spellbookid:"{variant.id}"',
                f'sid:{variant.id}',
            ]
            negative_queries = [
                f'spellbookid:"{variant.id[:-2] or "1"}"',
                f'sid:{variant.id[:-2] or "1"}',
            ]
            for q in queries:
                with self.subTest(f'query by variant id: {variant.id} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variant_count = 1
                    self.assertEqual(len(result.results), variant_count)
                    for i in range(variant_count):
                        self.variant_assertions(result.results[i])
            for q in negative_queries:
                with self.subTest(f'query by variant id: {variant.id} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self.assertEqual(len(result.results), 0)

    def test_variants_list_view_query_by_commander_name(self):
        for search in (c.name for c in Card.objects.filter(cardinvariant__must_be_commander=True)):
            prefix_without_spaces = search.partition(' ')[0]
            search_without_accents = search.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('Á', 'A').replace('É', 'E').replace('Í', 'I').replace('Ó', 'O').replace('Ú', 'U')
            search_with_simplfied_underscores_without_accents = search_without_accents.replace('_____', '_')
            queries = [
                (f'commander:{prefix_without_spaces}', models.Q(cardinvariant__card__name__icontains=prefix_without_spaces)),
                (f'commander:"{prefix_without_spaces}"', models.Q(cardinvariant__card__name__icontains=prefix_without_spaces)),
                (f'commander:"{search}"', models.Q(cardinvariant__card__name__icontains=search)),
                (f'commander:"{search_without_accents}"', models.Q(cardinvariant__card__name_unaccented__icontains=search_without_accents)),
                (f'commander:"{search_with_simplfied_underscores_without_accents}"', models.Q(cardinvariant__card__name_unaccented_simplified__icontains=search_with_simplfied_underscores_without_accents)),
                (f'commander={prefix_without_spaces}', models.Q(cardinvariant__card__name__iexact=prefix_without_spaces)),
                (f'commander="{prefix_without_spaces}"', models.Q(cardinvariant__card__name__iexact=prefix_without_spaces)),
                (f'commander="{search}"', models.Q(cardinvariant__card__name__iexact=search)),
                (f'commander="{search_without_accents}"', models.Q(cardinvariant__card__name_unaccented__iexact=search_without_accents)),
                (f'commander="{search_with_simplfied_underscores_without_accents}"', models.Q(cardinvariant__card__name_unaccented_simplified__iexact=search_with_simplfied_underscores_without_accents)),
            ]
            for q, q_django in queries:
                with self.subTest(f'query by commander name: {search} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants = self.public_variants.filter(q_django, cardinvariant__must_be_commander=True).distinct()
                    self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                    for v in result.results:
                        self.variant_assertions(v)

    def test_variants_list_view_query_by_legality(self):
        for legality in [f.removeprefix('legal_') for f in Variant.legalities_fields()]:
            queries = [
                (f'legal:{legality}', models.Q(**{f'legal_{legality}': True})),
                (f'format:{legality}', models.Q(**{f'legal_{legality}': True})),
                (f'banned:{legality}', models.Q(**{f'legal_{legality}': False})),
            ]
            for q, q_django in queries:
                with self.subTest(f'query by legality: {legality} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants = self.public_variants.filter(q_django).distinct()
                    self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                    for v in result.results:
                        self.variant_assertions(v)

    def test_variants_list_view_query_by_price(self):
        for price in range(10):
            queries = [
                (f'price={price}', models.Q(price_cardkingdom=price)),
                (f'price:{price}', models.Q(price_cardkingdom=price)),
                (f'price>={price}', models.Q(price_cardkingdom__gte=price)),
                (f'price<={price}', models.Q(price_cardkingdom__lte=price)),
                (f'price>{price}', models.Q(price_cardkingdom__gt=price)),
                (f'price<{price}', models.Q(price_cardkingdom__lt=price)),
                (f'usd={price}', models.Q(price_cardkingdom=price)),
                (f'usd:{price}', models.Q(price_cardkingdom=price)),
                (f'usd>={price}', models.Q(price_cardkingdom__gte=price)),
                (f'usd<={price}', models.Q(price_cardkingdom__lte=price)),
                (f'usd>{price}', models.Q(price_cardkingdom__gt=price)),
                (f'usd<{price}', models.Q(price_cardkingdom__lt=price)),
                (f'eur={price}', models.Q(price_cardmarket=price)),
                (f'eur:{price}', models.Q(price_cardmarket=price)),
                (f'eur>={price}', models.Q(price_cardmarket__gte=price)),
                (f'eur<={price}', models.Q(price_cardmarket__lte=price)),
                (f'eur>{price}', models.Q(price_cardmarket__gt=price)),
                (f'eur<{price}', models.Q(price_cardmarket__lt=price)),
                *[
                    x
                    for store in {s.removeprefix('price_') for s in Variant.prices_fields()}
                    for x in [
                        (f'{store}={price}', models.Q(**{f'price_{store}': price})),
                        (f'{store}:{price}', models.Q(**{f'price_{store}': price})),
                        (f'{store}>={price}', models.Q(**{f'price_{store}__gte': price})),
                        (f'{store}<={price}', models.Q(**{f'price_{store}__lte': price})),
                        (f'{store}>{price}', models.Q(**{f'price_{store}__gt': price})),
                        (f'{store}<{price}', models.Q(**{f'price_{store}__lt': price})),
                    ]
                ]
            ]
            for q, q_django in queries:
                with self.subTest(f'query by price: {price} with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_200_OK)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants = self.public_variants.filter(q_django).distinct()
                    self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                    for v in result.results:
                        self.variant_assertions(v)

    def test_variants_list_view_query_by_bracket(self):
        with self.subTest('query by bracket with number'):
            for bracket in range(1, 6):
                for operator, operator_django in self.operators.items():
                    queries = [
                        f'bracket{operator}{bracket}',
                        f'brackets{operator}{bracket}',
                        f'b{operator}{bracket}',
                    ]
                    for q in queries:
                        q_django = {f'bracket__{operator_django}': bracket}
                        with self.subTest(f'query by bracket: {bracket} with query {q}'):
                            response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                            self.assertEqual(response.status_code, status.HTTP_200_OK)
                            self.assertEqual(response.get('Content-Type'), 'application/json')
                            result = json.loads(response.content, object_hook=json_to_python_lambda)
                            variants = self.public_variants.filter(**q_django).distinct()
                            self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                            for v in result.results:
                                self.variant_assertions(v)
        with self.subTest('query by bracket with tag'):
            for value, bracket in Variant.BracketTag.choices:
                queries = [
                    f'bracket:{bracket}',
                    f'brackets={bracket}',
                    f'b:{bracket}',
                ]
                for q in queries:
                    with self.subTest(f'query by bracket: {bracket} with query {q}'):
                        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        self.assertEqual(response.get('Content-Type'), 'application/json')
                        result = json.loads(response.content, object_hook=json_to_python_lambda)
                        variants = self.public_variants.filter(bracket_tag=value).distinct()
                        self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                        for v in result.results:
                            self.variant_assertions(v)
        with self.subTest('query by bracket with invalid value'):
            queries = [
                'bracket<=invalid',
                'bracket>=invalid',
                'bracket<invalid',
                'bracket>invalid',
            ]
            for q in queries:
                with self.subTest(f'query by bracket with invalid value with query {q}'):
                    response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                    self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_variants_list_view_query_by_variants(self):
        for bracket in range(
            Variant.objects.values('variant_count').aggregate(models.Min('variant_count'))['variant_count__min'],
            Variant.objects.values('variant_count').aggregate(models.Max('variant_count'))['variant_count__max'],
        ):
            for operator, operator_django in self.operators.items():
                queries = [
                    f'variants{operator}{bracket}',
                ]
                for q in queries:
                    q_django = {f'variant_count__{operator_django}': bracket}
                    with self.subTest(f'query by bracket: {bracket} with query {q}'):
                        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                        self.assertEqual(response.status_code, status.HTTP_200_OK)
                        self.assertEqual(response.get('Content-Type'), 'application/json')
                        result = json.loads(response.content, object_hook=json_to_python_lambda)
                        variants = self.public_variants.filter(**q_django).distinct()
                        self.assertSetEqual({v.id for v in result.results}, {v.id for v in variants})
                        for v in result.results:
                            self.variant_assertions(v)

    def test_variants_list_view_query_by_a_combination_of_terms(self):
        queries = [
            ('result=FD A result:B', self.variants_matching_any_cards(Card.objects.filter(name__icontains='A')).filter(produces__name__iexact='FD').filter(produces__name__icontains='B').values_list('id', flat=True).distinct().order_by()),
            ('-card:a card:b -desc:easy', self.variants_matching_any_cards(Card.objects.filter(name__icontains='b')).exclude(uses__name__icontains='a').exclude(description__icontains='easy').exclude(status=Variant.Status.EXAMPLE).values_list('id', flat=True).distinct().order_by()),
        ]
        for q, variants in queries:
            with self.subTest(f'query by a combination of terms: {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertGreater(len(result.results), 0)
                self.assertSetEqual({v.id for v in result.results}, set(variants))
                for v in result.results:
                    self.variant_assertions(v)

    def query_ids(self, q: str) -> set[str]:
        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        for v in result.results:
            self.variant_assertions(v)
        return {v.id for v in result.results}

    def variant_ids_using_card_named(self, term: str) -> set[str]:
        matching_cards = Card.objects.filter(
            models.Q(name__icontains=term) | models.Q(name_unaccented__icontains=term) | models.Q(name_unaccented_simplified__icontains=term) | models.Q(name_unaccented_simplified_with_spaces__icontains=term)
        )
        return {v.id for v in self.variants_matching_any_cards(matching_cards)}

    def test_variants_list_view_query_by_or(self):
        a, b, c, d = (self.variant_ids_using_card_named(t) for t in 'abcd')
        everything = {v.id for v in self.public_variants.all()}
        self.assertGreater(len(a), 0)
        self.assertGreater(len(b), 0)
        self.assertNotEqual(a, b)
        queries = [
            ('card:a OR card:b', a | b),
            ('card:a or card:b', a | b),
            ('card:a Or card:b', a | b),
            ('card:a | card:b', a | b),
            ('card:a || card:b', a | b),
            ('card:a OR card:b OR card:c', a | b | c),
            ('card:a and card:b', a & b),
            ('card:a AND card:b', a & b),
            ('card:a card:b', a & b),
            ('(card:a card:b) OR (card:c card:d)', (a & b) | (c & d)),
            ('(card:a OR card:b) card:c', (a | b) & c),
            ('card:c (card:a OR card:b)', (a | b) & c),
            ('-(card:a OR card:b)', everything - (a | b)),
            ('-(card:a card:b)', everything - (a & b)),
            ('-card:a OR card:b', (everything - a) | b),
            ('card:a OR -card:b', a | (everything - b)),
            ('(card:a OR card:b) (card:c OR card:d)', (a | b) & (c | d)),
            ('((card:a OR card:b) card:c) OR card:d', ((a | b) & c) | d),
        ]
        for q, expected in queries:
            with self.subTest(f'query with or: {q}'):
                self.assertSetEqual(self.query_ids(q), expected)

    def test_variants_list_view_query_by_or_binds_looser_than_and(self):
        a, b, c = (self.variant_ids_using_card_named(t) for t in 'abc')
        shared = (a & b) | (a & c)
        # If OR bound tighter, `card:a card:b OR card:a card:c` would mean a AND (b OR a) AND c,
        # which is just a AND c. The seed data has to tell the two readings apart.
        self.assertNotEqual(shared, a & c, 'seed data cannot distinguish the two parses')
        self.assertGreater(len(shared), 0)
        queries = [
            ('card:a card:b OR card:a card:c', shared),
            ('card:a card:b or card:a card:c', shared),
            ('card:a AND card:b OR card:a AND card:c', shared),
            ('card:a card:b | card:a card:c', shared),
            ('card:a card:b OR card:c', (a & b) | c),
            ('card:a OR card:b card:c', a | (b & c)),
            ('card:a card:b OR card:a card:c OR card:b card:c', (a & b) | (a & c) | (b & c)),
        ]
        for q, expected in queries:
            with self.subTest(f'and binds tighter than or: {q}'):
                self.assertSetEqual(self.query_ids(q), expected)
        with self.subTest('the implicit grouping matches the explicit one'):
            self.assertSetEqual(
                self.query_ids('card:a card:b OR card:a card:c'),
                self.query_ids('(card:a card:b) OR (card:a card:c)'),
            )

    def variant_ids_matching_any_card(self, card_q: models.Q) -> set[str]:
        return {v.id for v in self.variants_matching_any_cards(Card.objects.filter(card_q))}

    def variant_ids_matching_all_cards(self, card_q: models.Q) -> set[str]:
        return {v.id for v in self.variants_matching_all_cards(Card.objects.filter(card_q))}

    def test_variants_list_view_query_by_convoluted_expressions(self):
        # `any_*` is "uses some card matching", `all_*` is the @ prefix, "every card matches".
        # No card-name term gives a non-empty all-of set here, since every variant uses several
        # differently named cards, so the all-of side is driven by oracle text instead.
        any_a, any_b, any_c = (self.variant_ids_using_card_named(t) for t in 'abc')
        oracle_x = models.Q(oracle_text__icontains='x')
        any_x = self.variant_ids_matching_any_card(oracle_x)
        all_x = self.variant_ids_matching_all_cards(oracle_x)
        all_instant = self.variant_ids_matching_all_cards(models.Q(type_line__icontains='instant'))
        everything = {v.id for v in self.public_variants.all()}
        for name, subset in (('any_a', any_a), ('any_b', any_b), ('any_c', any_c), ('all_x', all_x)):
            self.assertGreater(len(subset), 0, f'{name} must be non-empty for this test to mean anything')
        self.assertNotEqual(all_x, any_x, 'the @ prefix must differ from a plain search here')
        self.assertNotEqual(all_x, everything, 'the @ prefix must exclude something here')
        queries = [
            # the all-of operator against and/or
            ('@o:x', all_x),
            ('@o:x @t:instant', all_x & all_instant),
            ('@o:x OR @t:instant', all_x | all_instant),
            ('@o:x OR card:a', all_x | any_a),
            ('@o:x card:a', all_x & any_a),
            # negation against the all-of operator
            ('-@o:x', everything - all_x),
            ('-@o:x -@t:instant', everything - all_x - all_instant),
            ('-@o:x OR -@t:instant', (everything - all_x) | (everything - all_instant)),
            ('-(@o:x OR @t:instant)', everything - (all_x | all_instant)),
            ('-(@o:x @t:instant)', everything - (all_x & all_instant)),
            ('@o:x -card:a', all_x - any_a),
            ('-@o:x card:a', (everything - all_x) & any_a),
            # negation against and/or
            ('-card:a -card:b', everything - any_a - any_b),
            ('-card:a OR -card:b', (everything - any_a) | (everything - any_b)),
            ('-(card:a OR card:b)', everything - (any_a | any_b)),
            ('-(card:a card:b)', everything - (any_a & any_b)),
            ('-(-card:a)', any_a),
            ('-(-card:a OR -card:b)', any_a & any_b),
            ('-(-card:a -card:b)', any_a | any_b),
            # all three together
            ('(@o:x OR -card:a) card:b', (all_x | (everything - any_a)) & any_b),
            ('(card:a card:b) OR (@o:x -card:c)', (any_a & any_b) | (all_x - any_c)),
            ('-((@o:x card:a) OR (-card:b card:c))', everything - ((all_x & any_a) | ((everything - any_b) & any_c))),
            ('(-card:a OR @o:x) (card:b OR -card:c)', ((everything - any_a) | all_x) & (any_b | (everything - any_c))),
            ('((card:a OR card:b) (card:c OR @o:x)) OR (-card:a -card:b)', ((any_a | any_b) & (any_c | all_x)) | (everything - any_a - any_b)),
        ]
        for q, expected in queries:
            with self.subTest(f'convoluted query: {q}'):
                self.assertSetEqual(self.query_ids(q), expected)

    def test_variants_list_view_query_by_or_keeps_term_guards_local(self):
        combo = Combo.objects.first()
        prereq = (combo.notable_prerequisites + '\n' + combo.easy_prerequisites).split(maxsplit=2)[0]  # type: ignore
        example = self.public_variants.filter(status=Variant.Status.EXAMPLE).first()
        self.assertIsNotNone(example)
        example_card: Card = example.uses.first()  # type: ignore
        reachable_by_card = self.variant_ids_using_card_named(example_card.name)
        self.assertIn(example.id, reachable_by_card)  # type: ignore
        matching_prereq = {v.id for v in self.ok_variants.filter(
            models.Q(easy_prerequisites__icontains=prereq) | models.Q(notable_prerequisites__icontains=prereq)
        )}
        with self.subTest('a prerequisites search never matches example variants'):
            self.assertSetEqual(self.query_ids(f'pre:{prereq}'), matching_prereq)
        with self.subTest('negating it still never matches example variants'):
            not_matching_prereq = {v.id for v in self.ok_variants.exclude(
                models.Q(easy_prerequisites__icontains=prereq) | models.Q(notable_prerequisites__icontains=prereq)
            )}
            self.assertSetEqual(self.query_ids(f'-pre:{prereq}'), not_matching_prereq)
        with self.subTest('the guard does not leak onto the other side of an or'):
            self.assertSetEqual(
                self.query_ids(f'pre:{prereq} OR card:"{example_card.name}"'),
                matching_prereq | reachable_by_card,
            )

    def test_variants_list_view_query_by_spellbook_id_with_multiple_aliases(self):
        variant = self.public_variants.first()
        for i in range(3):
            VariantAlias.objects.create(id=f'alias-{i}', variant=variant)
        with self.subTest('a variant with several aliases is returned once'):
            self.assertSetEqual(self.query_ids(f'sid:{variant.id}'), {variant.id})  # type: ignore
        with self.subTest('each alias resolves to the variant'):
            for i in range(3):
                self.assertSetEqual(self.query_ids(f'sid:alias-{i}'), {variant.id})  # type: ignore

    def test_variants_list_view_query_with_invalid_or(self):
        queries = [
            'card:a OR',
            '(card:a OR card:b',
            'card:a OR card:b)',
            'card:a OR |',
        ]
        for q in queries:
            with self.subTest(f'invalid query: {q}'):
                response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_variants_list_view_query_with_or_where_an_operator_cannot_go(self):
        # Where OR cannot be an operator the lexer falls back to a card name search, so a card
        # actually named "or" stays reachable.
        or_named = self.variant_ids_using_card_named('or')
        a = self.variant_ids_using_card_named('a')
        b = self.variant_ids_using_card_named('b')
        with self.subTest('a lone OR searches for a card named or'):
            self.assertSetEqual(self.query_ids('OR'), or_named)
        with self.subTest('a doubled OR searches for a card named or'):
            self.assertSetEqual(self.query_ids('card:a OR OR card:b'), a | (or_named & b))

    def test_variants_list_view_query_with_too_many_or_terms(self):
        q = ' OR '.join(f'card:{i}' for i in range(21))
        response = self.client.get(reverse('variants-list'), query_params={'q': q}, follow=True)  # type: ignore
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Too many search parameters.', json.loads(response.content)['q'])

    def test_variants_query_fuses_subqueries_on_the_same_entity(self):
        # A disjunction of conditions on one entity is a single EXISTS. Nothing in the results
        # reveals this, but losing it costs two orders of magnitude once an OR sits under an AND.
        queries = [
            ('card:a', 1),
            ('card:a OR card:b', 1),
            ('card:a OR card:b OR card:c', 1),
            ('t:x OR card:y', 1),
            ('results:a OR results:b', 1),
            ('template:a OR template:b', 1),
            ('-(card:a OR card:b)', 1),
            ('-card:a -card:b', 1),
            ('ci:temur OR ci:mardu', 0),
            ('card:a card:b', 2),
            ('card:a OR -card:b', 2),
            ('is:commander OR card:a', 2),
            ('(card:a OR card:b) (card:c OR card:d)', 2),
            ('(card:a card:b) OR (card:c card:d)', 4),
        ]
        for q, expected in queries:
            with self.subTest(f'subqueries for: {q}'):
                queryset = variants_query_parser(self.public_variants.all(), q)
                sql, _ = queryset.query.get_compiler(using='default').as_sql()
                self.assertEqual(sql.count('EXISTS'), expected)

    def test_variants_query_factors_conditions_shared_by_every_branch(self):
        # `(A B) OR (A C)` evaluates A once, and leaves B and C under one OR where they fuse.
        # Only the compiled SQL shows this, so the counts are the assertion.
        queries = [
            ('card:a card:b OR card:a card:c', 2),
            ('card:a card:b OR card:a card:c OR card:a card:d', 2),
            ('desc:a card:b OR desc:a card:c', 1),
            ('t:a o:b results:c OR t:a o:b results:d', 3),
            ('ci:temur card:a OR ci:temur card:b', 1),
            ('pre:x OR pre:y', 0),
            # absorption: a branch left with nothing means the shared conditions imply the rest
            ('card:a card:b OR card:a', 1),
            ('card:a OR card:a card:b', 1),
            # idempotence
            ('card:a card:a', 1),
            ('card:a OR card:a', 1),
            ('(card:a OR card:b) (card:a OR card:b)', 1),
            # nothing shared, so nothing to lift
            ('(card:a card:b) OR (card:c card:d)', 4),
        ]
        for q, expected in queries:
            with self.subTest(f'subqueries for: {q}'):
                queryset = variants_query_parser(self.public_variants.all(), q)
                sql, _ = queryset.query.get_compiler(using='default').as_sql()
                self.assertEqual(sql.count('EXISTS'), expected)

    def test_variants_query_rewrites_reach_spellbook_id_terms(self):
        # The alias lookup is a node rather than a subquery hidden in a Q, so two identical `sid:`
        # terms compare equal and the rewrites apply to them like any other condition.
        variant = self.public_variants.first()
        sid = f'sid:{variant.id}'  # type: ignore
        queries = [
            (sid, 1),
            (f'{sid} OR {sid}', 1),
            (f'{sid} {sid}', 1),
            (f'{sid} card:a OR {sid} card:b', 2),
            (f'{sid} OR card:a', 2),
        ]
        for q, expected in queries:
            with self.subTest(f'subqueries for: {q}'):
                queryset = variants_query_parser(self.public_variants.all(), q)
                sql, _ = queryset.query.get_compiler(using='default').as_sql()
                self.assertEqual(sql.count('EXISTS'), expected)
        with self.subTest('results are unaffected'):
            self.assertSetEqual(self.query_ids(sid), {variant.id})  # type: ignore
            self.assertSetEqual(self.query_ids(f'{sid} OR {sid}'), {variant.id})  # type: ignore

    def test_variants_query_rewrites_do_not_change_results(self):
        a, b, c = (self.variant_ids_using_card_named(t) for t in 'abc')
        self.assertGreater(len((a & b) | (a & c)), 0)
        queries = [
            ('card:a card:b OR card:a card:c', (a & b) | (a & c)),
            ('card:a (card:b OR card:c)', (a & b) | (a & c)),
            ('card:a card:b OR card:a card:c OR card:a', a),
            ('card:a card:b OR card:a', a),
            ('card:a OR card:a card:b', a),
            ('card:a card:a', a),
            ('card:a OR card:a', a),
            ('(card:a OR card:b) (card:a OR card:b)', a | b),
            ('card:a card:b card:c OR card:a card:b', a & b),
        ]
        for q, expected in queries:
            with self.subTest(f'rewritten query still matches: {q}'):
                self.assertSetEqual(self.query_ids(q), expected)

    def test_variants_query_factoring_keeps_term_guards(self):
        combo = Combo.objects.first()
        prereqs = (combo.notable_prerequisites + '\n' + combo.easy_prerequisites).split()  # type: ignore
        first, second = prereqs[0], prereqs[-1]
        # Both branches carry the same "not an example variant" guard, so factoring lifts it out.
        # It has to keep applying to both.
        matches_first = models.Q(easy_prerequisites__icontains=first) | models.Q(notable_prerequisites__icontains=first)
        matches_second = models.Q(easy_prerequisites__icontains=second) | models.Q(notable_prerequisites__icontains=second)
        expected = {v.id for v in self.ok_variants.filter(matches_first | matches_second)}
        self.assertSetEqual(self.query_ids(f'pre:{first} OR pre:{second}'), expected)
        self.assertFalse(
            expected & {v.id for v in self.public_variants.filter(status=Variant.Status.EXAMPLE)},
            'a prerequisites search must never return example variants',
        )

    def seed_popularity(self) -> list[Variant]:
        variants = list[Variant](Variant.objects.all())
        for popularity, variant in enumerate(variants):
            variant.popularity = popularity if popularity > 0 else None  # pyright: ignore[reportAttributeAccessIssue]
        self.bulk_serialize_variants(q=variants, extra_fields=['popularity'])
        return variants

    def test_variants_list_view_ordering_by_popularity_with_nulls(self):
        self.seed_popularity()
        for order in ('popularity', '-popularity'):
            with self.subTest(f'order by {order}'):
                response = self.client.get(reverse('variants-list'), data={'ordering': order}, follow=True)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                self.assertGreater(len(result.results), 1)
                self.assertIsNotNone(result.results[0].popularity)

    def test_variants_list_view_grouping_by_combo(self):
        parameter = VariantGroupedByComboFilter.query_param
        variants = self.seed_popularity()
        variant_count = len(variants)
        best_variants_ids = set[str]()
        for combo in Combo.objects.filter(status=Combo.Status.GENERATOR):
            best_variant = combo.variants.order_by('-popularity').first()  # type: ignore
            if best_variant:
                best_variants_ids.add(best_variant.id)
        self.assertLess(len(best_variants_ids), variant_count)
        with self.subTest('without parameter'):
            response = self.client.get(reverse('variants-list'), query_params={'ordering': '-popularity', 'count': True}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            self.assertEqual(result.count, variant_count)
            result_id_set = {v.id for v in result.results}
            self.assertTrue(result_id_set.issuperset(best_variants_ids) and result_id_set != best_variants_ids)
        with self.subTest('with false value'):
            response = self.client.get(reverse('variants-list'), query_params={parameter: 'false', 'ordering': '-popularity', 'count': True}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            self.assertEqual(result.count, variant_count)
            result_id_set = {v.id for v in result.results}
            self.assertTrue(result_id_set.issuperset(best_variants_ids) and result_id_set != best_variants_ids)
        with self.subTest('with true value'):
            response = self.client.get(reverse('variants-list'), query_params={parameter: 'true', 'ordering': '-popularity', 'count': True}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.get('Content-Type'), 'application/json')
            result = json.loads(response.content, object_hook=json_to_python_lambda)
            self.assertEqual(result.count, len(best_variants_ids))
            result_id_set = {v.id for v in result.results}
            self.assertSetEqual(result_id_set, best_variants_ids)

    def test_variants_list_view_grouping_by_combo_windowing(self):
        parameter = VariantGroupedByComboFilter.query_param
        self.seed_popularity()

        def paged_ids(query_params):
            paged, offset = [], 0
            while True:
                response = self.client.get(reverse('variants-list'), query_params=query_params | {'limit': 2, 'offset': offset}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                page = [v.id for v in json.loads(response.content, object_hook=json_to_python_lambda).results]
                paged.extend(page)
                if len(page) < 2:
                    return paged
                offset += 2

        for ordering in ('-popularity', 'card_count', '-created', 'variant_count'):
            query_params = {parameter: 'true', 'ordering': ordering}
            response = self.client.get(reverse('variants-list'), query_params=query_params | {'count': True}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            reference = [v.id for v in json.loads(response.content, object_hook=json_to_python_lambda).results]
            self.assertGreater(len(reference), 2)
            with self.subTest(f'ordering by {ordering} through computed windows'):
                self.assertEqual(paged_ids(query_params), reference)
            with self.subTest(f'ordering by {ordering} through windows too narrow to fill a page'):
                with patch.object(VariantGroupedByComboFilter, 'window_size_for', lambda *_: 1):
                    self.assertEqual(paged_ids(query_params), reference)

    def test_variants_list_view_variant_filter(self):
        for variant_id in Variant.objects.values_list('pk', flat=True):
            with self.subTest(f'combo {variant_id}'):
                response = self.client.get(reverse('variants-list'), query_params={'variant': variant_id}, follow=True)  # type: ignore
                self.assertEqual(response.status_code, status.HTTP_200_OK, response.content.decode())
                self.assertEqual(response.get('Content-Type'), 'application/json')
                result = json.loads(response.content, object_hook=json_to_python_lambda)
                result_id_set = {v.id for v in result.results}
                correct_id_set = {v.id for v in Variant.objects.filter(of__variants=variant_id)}
                self.assertSetEqual(result_id_set, correct_id_set)
