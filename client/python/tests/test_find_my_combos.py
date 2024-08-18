from .testing import SpellbookClientTest
from ..spellbook_client.models.deck_request import DeckRequest
from spellbook.models.utils import id_from_cards_and_templates_ids


class TestFindMyCombos(SpellbookClientTest):
    async def test_with_json_body(self):
        result = await self.spellbook_client_anonymous.find_my_combos.post(
            body=DeckRequest(
                commanders=[
                    'F F',
                ],
                main=[
                    'B B',
                    'C C',
                    'E É',
                ],
            )
        )
        self.assertEqual(result.results.identity, 'GWUB')
        self.assertSetEqual({id_from_cards_and_templates_ids([self.c2_id, self.c3_id, self.c5_id, self.c6_id], []), id_from_cards_and_templates_ids([self.c2_id, self.c3_id, self.c5_id, self.c6_id], [self.t1_id])}, {v.id for v in result.results.included})
        self.assertSetEqual(set(), {v.id for v in result.results.included_by_changing_commanders})
        self.assertSetEqual({id_from_cards_and_templates_ids([self.c1_id, self.c2_id, self.c3_id], []), id_from_cards_and_templates_ids([self.c1_id, self.c2_id, self.c3_id], [self.t1_id])}, {v.id for v in result.results.almost_included})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_changing_commanders})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors_and_changing_commanders})

    async def test_with_json_body_but_empty(self):
        result = await self.spellbook_client_anonymous.find_my_combos.post(
            body=DeckRequest(
                commanders=[],
                main=[],
            )
        )
        self.assertEqual(result.results.identity, 'C')
        self.assertSetEqual(set(), {v.id for v in result.results.included})
        self.assertSetEqual(set(), {v.id for v in result.results.included_by_changing_commanders})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_changing_commanders})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors_and_changing_commanders})
