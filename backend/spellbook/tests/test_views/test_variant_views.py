import json
from django.test import Client
from spellbook.utils import launch_job_command
from spellbook.models import Card, Template, Feature, Variant, CardInVariant, TemplateInVariant
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class VariantViewsTests(AbstractModelTests):
    def setUp(self) -> None:
        super().setUp()
        launch_job_command('generate_variants', None)
        Variant.objects.update(status=Variant.Status.OK)
        self.v1_id = Variant.objects.first().id

    def variant_assertions(self, variant_result):
        v = Variant.objects.get(id=variant_result.id)
        self.assertEqual(variant_result.id, v.id)
        self.assertEqual(variant_result.identity, v.identity)
        self.assertEqual(variant_result.mana_needed, v.mana_needed)
        self.assertEqual(variant_result.other_prerequisites, v.other_prerequisites)
        self.assertEqual(variant_result.description, v.description)
        self.assertEqual(variant_result.legal, v.legal)
        self.assertEqual(variant_result.spoiler, v.spoiler)
        uses_list = [u.id for u in v.uses.all()]
        for u in variant_result.uses:
            card = u.card
            self.assertIn(card.id, uses_list)
            c = Card.objects.get(id=card.id)
            self.assertEqual(card.id, c.id)
            self.assertEqual(card.name, c.name)
            self.assertEqual(card.oracle_id, str(c.oracle_id))
            self.assertEqual(card.identity, c.identity)
            self.assertEqual(card.legal, c.legal)
            self.assertEqual(card.spoiler, c.spoiler)
            vic = CardInVariant.objects.get(variant=v.id, card=c)
            self.assertEqual(set(u.zone_locations), set(vic.zone_locations))
            self.assertEqual(u.card_state, vic.card_state)
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
            self.assertEqual(r.card_state, tiv.card_state)
        produces_list = [p.id for p in v.produces.all()]
        for p in variant_result.produces:
            self.assertIn(p.id, produces_list)
            f = Feature.objects.get(id=p.id)
            self.assertEqual(p.id, f.id)
            self.assertEqual(p.name, f.name)
            self.assertEqual(p.utility, f.utility)
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
