import json
import random
from django.db import models
from django.urls import reverse
from rest_framework import status
from common.inspection import json_to_python_lambda
from spellbook.models import Card, Template, Feature, Variant, CardInVariant, TemplateInVariant, Combo
from spellbook.models.utils import SORTED_COLORS
from spellbook.views import VariantViewSet
from spellbook.serializers import VariantSerializer
from spellbook.views.variants import VariantGroupedByComboFilter
from website.models import WebsiteProperty, FEATURED_SET_CODES_PROPERTIES
from ..testing import SpellbookTestCaseWithSeeding


class VariantViewsTests(SpellbookTestCaseWithSeeding):
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
        cls.public_variants = VariantViewSet.queryset
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
        self.assertEqual(variant_result.legalities.brawl, v.legal_brawl)
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
        with self.subTest('Test all- prefix in combination with card_count'):
            response = self.client.get(reverse('variants-list'), query_params={'q': f'all-cards:{2}'}, follow=True)  # type: ignore
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

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
        for bracket in range(1, 6):
            for operator, operator_django in self.operators.items():
                queries = [
                    f'bracket{operator}{bracket}',
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

    def seed_popularity(self) -> list[Variant]:
        variants = list[Variant](Variant.objects.all())
        for popularity, variant in enumerate(variants):
            variant.popularity = popularity if popularity > 0 else None
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
