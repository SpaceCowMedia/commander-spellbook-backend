import json
from django.test import Client
from spellbook.models import Card, Feature, Template, Combo, CardInCombo, TemplateInCombo
from ..abstract_test import AbstractModelTests
from ..inspection import json_to_python_lambda


class ComboViewsTests(AbstractModelTests):
    def combo_assertions(self, combo_result):
        b = Combo.objects.get(id=combo_result.id)
        self.assertEqual(combo_result.id, b.id)
        self.assertEqual(combo_result.mana_needed, b.mana_needed)
        self.assertEqual(combo_result.other_prerequisites, b.other_prerequisites)
        self.assertEqual(combo_result.description, b.description)
        self.assertEqual(len(combo_result.requires), b.requires.count())
        produces_list = [p.id for p in b.produces.all()]
        for p in combo_result.produces:
            self.assertIn(p.id, produces_list)
            f = Feature.objects.get(id=p.id)
            self.assertEqual(p.name, f.name)
            self.assertEqual(p.description, f.description)
            self.assertEqual(p.utility, f.utility)
        needs_list = [n.id for n in b.needs.all()]
        for n in combo_result.needs:
            self.assertIn(n.id, needs_list)
            f = Feature.objects.get(id=n.id)
            self.assertEqual(n.name, f.name)
            self.assertEqual(n.description, f.description)
            self.assertEqual(n.utility, f.utility)
        uses_list = [u.id for u in b.uses.all()]
        for u in combo_result.uses:
            card = u.card
            self.assertIn(card.id, uses_list)
            c = Card.objects.get(id=card.id)
            self.assertEqual(card.id, c.id)
            self.assertEqual(card.name, c.name)
            self.assertEqual(card.oracle_id, str(c.oracle_id))
            self.assertEqual(card.identity, c.identity)
            self.assertEqual(card.legal, c.legal)
            self.assertEqual(card.spoiler, c.spoiler)
            cic = CardInCombo.objects.get(combo=b.id, card=c)
            self.assertEqual(set(u.zone_locations), set(cic.zone_locations))
            self.assertEqual(u.battlefield_card_state, cic.battlefield_card_state)
            self.assertEqual(u.exile_card_state, cic.exile_card_state)
            self.assertEqual(u.library_card_state, cic.library_card_state)
            self.assertEqual(u.graveyard_card_state, cic.graveyard_card_state)
        requires_list = [r.id for r in b.requires.all()]
        for r in combo_result.requires:
            template = r.template
            self.assertIn(template.id, requires_list)
            t = Template.objects.get(id=template.id)
            self.assertEqual(template.id, t.id)
            self.assertEqual(template.name, t.name)
            self.assertEqual(template.scryfall_query, t.scryfall_query)
            self.assertEqual(template.scryfall_api, t.scryfall_api())
            tic = TemplateInCombo.objects.get(combo=b.id, template=t)
            self.assertEqual(set(r.zone_locations), set(tic.zone_locations))
            self.assertEqual(r.battlefield_card_state, tic.battlefield_card_state)
            self.assertEqual(r.exile_card_state, tic.exile_card_state)
            self.assertEqual(r.library_card_state, tic.library_card_state)
            self.assertEqual(r.graveyard_card_state, tic.graveyard_card_state)

    def test_combos_list_view(self):
        c = Client()
        response = c.get('/combos', follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        combos_count = Combo.objects.count()
        self.assertEqual(len(result.results), combos_count)
        for i in range(combos_count):
            self.combo_assertions(result.results[i])

    def test_combos_detail_view(self):
        c = Client()
        response = c.get('/combos/{}'.format(self.b1_id), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')
        result = json.loads(response.content, object_hook=json_to_python_lambda)
        self.assertEqual(result.id, self.b1_id)
        self.combo_assertions(result)
