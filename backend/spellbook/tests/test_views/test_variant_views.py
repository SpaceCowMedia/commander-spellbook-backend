import json
import random
from django.test import Client
from spellbook.models import Card, Template, Feature, Variant, CardInVariant, TemplateInVariant
from ..abstract_test import AbstractModelTests
from common.inspection import json_to_python_lambda


class VariantViewsTests(AbstractModelTests):
    def setUp(self) -> None:
        super().setUp()
        super().generate_variants()
        Variant.objects.update(status=Variant.Status.OK)
        Variant.objects.filter(id__in=random.sample(list(Variant.objects.values_list('id', flat=True)), 3)).update(status=Variant.Status.EXAMPLE)
        self.v1_id = Variant.objects.first().id

    def variant_assertions(self, variant_result):
        v = Variant.objects.get(id=variant_result.id)
        self.assertEqual(variant_result.id, v.id)
        self.assertEqual(variant_result.status, v.status)
        self.assertEqual(variant_result.identity, v.identity)
        self.assertEqual(variant_result.popularity, v.popularity)
        if v.status != Variant.Status.OK:
            self.assertEqual(variant_result.mana_needed, None)
            self.assertEqual(variant_result.other_prerequisites, None)
            self.assertEqual(variant_result.description, None)
        else:
            self.assertEqual(variant_result.mana_needed, v.mana_needed)
            self.assertEqual(variant_result.other_prerequisites, v.other_prerequisites)
            self.assertEqual(variant_result.description, v.description)
        self.assertEqual(variant_result.legalities.commander, v.legal_commander)
        self.assertEqual(variant_result.legalities.pauper_commander_main, v.legal_pauper_commander_main)
        self.assertEqual(variant_result.legalities.pauper_commander, v.legal_pauper_commander)
        self.assertEqual(variant_result.legalities.oathbreaker, v.legal_oathbreaker)
        self.assertEqual(variant_result.legalities.predh, v.legal_predh)
        self.assertEqual(variant_result.legalities.brawl, v.legal_brawl)
        self.assertEqual(variant_result.legalities.vintage, v.legal_vintage)
        self.assertEqual(variant_result.legalities.legacy, v.legal_legacy)
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
            vic = CardInVariant.objects.get(variant=v.id, card=c)
            if v.status != Variant.Status.OK:
                self.assertEqual(u.zone_locations, None)
                self.assertEqual(u.battlefield_card_state, None)
                self.assertEqual(u.exile_card_state, None)
                self.assertEqual(u.library_card_state, None)
                self.assertEqual(u.graveyard_card_state, None)
                self.assertEqual(u.must_be_commander, None)
            else:
                self.assertEqual(set(u.zone_locations), set(vic.zone_locations))
                self.assertEqual(u.battlefield_card_state, vic.battlefield_card_state)
                self.assertEqual(u.exile_card_state, vic.exile_card_state)
                self.assertEqual(u.library_card_state, vic.library_card_state)
                self.assertEqual(u.graveyard_card_state, vic.graveyard_card_state)
                self.assertEqual(u.must_be_commander, vic.must_be_commander)
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
            if v.status != Variant.Status.OK:
                self.assertEqual(r.zone_locations, None)
                self.assertEqual(r.battlefield_card_state, None)
                self.assertEqual(r.exile_card_state, None)
                self.assertEqual(r.library_card_state, None)
                self.assertEqual(r.graveyard_card_state, None)
                self.assertEqual(r.must_be_commander, None)
            else:
                self.assertEqual(set(r.zone_locations), set(tiv.zone_locations))
                self.assertEqual(r.battlefield_card_state, tiv.battlefield_card_state)
                self.assertEqual(r.exile_card_state, tiv.exile_card_state)
                self.assertEqual(r.library_card_state, tiv.library_card_state)
                self.assertEqual(r.graveyard_card_state, tiv.graveyard_card_state)
                self.assertEqual(r.must_be_commander, tiv.must_be_commander)
        produces_list = [p.id for p in v.produces.all()]
        for p in variant_result.produces:
            self.assertIn(p.id, produces_list)
            f = Feature.objects.get(id=p.id)
            self.assertEqual(p.id, f.id)
            self.assertEqual(p.name, f.name)
            self.assertEqual(p.description, f.description)
        of_list = [o.id for o in v.of.all()]
        for o in variant_result.of:
            self.assertIn(o.id, of_list)
        includes_list = [i.id for i in v.includes.all()]
        for i in variant_result.includes:
            self.assertIn(i.id, includes_list)

    def test_variants_list_view(self):
        c = Client()
        response = c.get('/variants', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        variants_count = Variant.objects.count()
        self.assertEqual(len(result.results), variants_count)
        for i in range(variants_count):
            self.variant_assertions(result.results[i])

    def test_variants_detail_view(self):
        c = Client()
        response = c.get('/variants/{}'.format(self.v1_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.v1_id)
        self.variant_assertions(result)

    def test_variants_list_view_query_by_card_name(self):
        c = Client()
        for card, search in ((c, name) for c in Card.objects.all() for name in (c.name, c.name_unaccented, c.name_unaccented.replace('-', ''), c.name_unaccented.replace('-', ' '))):
            prefix_without_spaces = search.partition(' ')[0]
            search_without_underscores = search.replace('_', '').strip()
            search_with_simplified_underscores = search.replace('_____', '_')
            queries = [
                prefix_without_spaces,
                f'"{prefix_without_spaces}"',
                f'"{search}"',
                f'"{search_without_underscores}"',
                f'"{search_with_simplified_underscores}"',
                f'card:{prefix_without_spaces}',
                f'card:"{prefix_without_spaces}"',
                f'card:"{search}"',
            ]
            queries = list(dict.fromkeys(queries))
            # case insensitive queries: isascii() is used to filter out case insensitive accented queries, incompatible with sqlite:
            # https://docs.djangoproject.com/en/5.0/ref/databases/#substring-matching-and-case-sensitivity
            queries += [q.upper() for q in queries if not q.isupper() and q.isascii()] + [q.lower() for q in queries if not q.islower() and q.isascii()]
            for q in queries:
                with self.subTest(f'query by card name: {search} with query {q}'):
                    response = c.get('/variants', data={'q': q}, follow=True)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants_count = Variant.objects.filter(uses__id=card.id).distinct().count()
                    self.assertEqual(len(result.results), variants_count)
                    for i in range(variants_count):
                        self.variant_assertions(result.results[i])

    def test_variants_list_view_query_by_card_count(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_card_type(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_card_oracle_text(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_card_keywords(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_card_mana_value(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_identity(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_prerequisites(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_steps(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_results(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_tag(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_spellbook_id(self):
        c = Client()
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
                    response = c.get('/variants', data={'q': q}, follow=True)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    variants_count = 1
                    self.assertEqual(len(result.results), variants_count)
                    for i in range(variants_count):
                        self.variant_assertions(result.results[i])
            for q in negative_queries:
                with self.subTest(f'query by variant id: {variant.id} with query {q}'):
                    response = c.get('/variants', data={'q': q}, follow=True)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get('Content-Type'), 'application/json')
                    result = json.loads(response.content, object_hook=json_to_python_lambda)
                    self.assertEqual(len(result.results), 0)

    def test_variants_list_view_query_by_commander_name(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_legality(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_price(self):
        # TODO: implement
        pass

    def test_variants_list_view_query_by_a_combination_of_terms(self):
        # TODO: implement
        pass
