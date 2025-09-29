from .testing import SpellbookClientTest
from spellbook_client import DeckRequest, CardInDeckRequest, PaginatedFindMyCombosResponseList, FindMyCombosApi
from spellbook_client.extensions import find_my_combos_create_plain
from spellbook.models.utils import id_from_cards_and_templates_ids
from textwrap import dedent


class TestFindMyCombos(SpellbookClientTest):
    def find_my_combos_assertions(self, result: PaginatedFindMyCombosResponseList):
        self.assertIsNotNone(result)
        self.assertEqual(result.results.identity, 'GWUB')
        self.assertSetEqual({
            id_from_cards_and_templates_ids(
                [self.c2_id, self.c3_id, self.c5_id, self.c6_id],
                []
            ),
            id_from_cards_and_templates_ids(
                [self.c2_id, self.c3_id, self.c5_id, self.c6_id],
                [self.t1_id]
            ),
        }, {v.id for v in result.results.included})
        self.assertSetEqual(set(), {v.id for v in result.results.included_by_changing_commanders})
        self.assertSetEqual({
            id_from_cards_and_templates_ids(
                [self.c1_id, self.c2_id, self.c3_id],
                []
            ),
            id_from_cards_and_templates_ids(
                [self.c1_id, self.c2_id, self.c3_id],
                [self.t1_id],
            ),
            id_from_cards_and_templates_ids(
                [self.c1_id, self.c2_id],
                [self.t1_id, self.t2_id],
            ),
        }, {v.id for v in result.results.almost_included})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_changing_commanders})
        self.assertSetEqual(set(), {v.id for v in result.results.almost_included_by_adding_colors_and_changing_commanders})

    async def test_with_json_body(self):
        async with self.anonymous_api_client as api_client:
            api_instance = FindMyCombosApi(api_client)
            result = await api_instance.find_my_combos_create(
                deck_request=DeckRequest(
                    commanders=[
                        CardInDeckRequest(card='F F'),
                    ],
                    main=[
                        CardInDeckRequest(card='B B'),
                        CardInDeckRequest(card='C C'),
                        CardInDeckRequest(card='E É'),
                    ],
                ),
            )
            self.find_my_combos_assertions(result)

    async def test_with_plain_text_body(self):
        async with self.anonymous_api_client as api_client:
            api_instance = FindMyCombosApi(api_client)
            result = await find_my_combos_create_plain(
                api_instance,
                decklist=dedent(  # type: ignore
                    '''
                    // Commander
                    1x F F
                    // Main
                    1x B B
                    1x C C
                    1x E É
                    ''',
                ),
            )
            self.find_my_combos_assertions(result)

    async def test_with_json_body_but_empty(self):
        async with self.anonymous_api_client as api_client:
            api_instance = FindMyCombosApi(api_client)
            result = await api_instance.find_my_combos_create(
                deck_request=DeckRequest(
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
