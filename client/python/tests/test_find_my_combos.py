from .testing import SpellbookClientTest
from ..models.deck_request import DeckRequest


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
        self.assertSetEqual({'2-3-5-6', '2-3-5-6--1'}, {v.id for v in result.results.included})
        self.assertSetEqual(set(), {v.id for v in result.results.included_by_changing_commanders})
