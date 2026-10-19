'''The bot against a fake backend, whose responses carry fields the client does not know about.'''
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch
from discord import ui
from tests.fake_backend import FakeBackend
from tests.samples import sample, variant_sample, paginated_sample
from constants import WEBSITE_URL
import spellbook_discord


def texts(view: ui.LayoutView) -> str:
    return '\n'.join(item.content for item in view.walk_children() if isinstance(item, ui.TextDisplay))


def fake_interaction() -> MagicMock:
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message = None
    interaction.context.dm_channel = False
    interaction.is_guild_integration.return_value = True
    return interaction


def find_my_combos_sample(included: list[dict], almost_included: list[dict]) -> dict:
    response = sample('PaginatedFindMyCombosResponseList', unexpected_fields=True)
    response['results'].update(
        identity='UB',
        included=included,
        includedByChangingCommanders=[],
        almostIncluded=almost_included,
        almostIncludedByAddingColors=[],
        almostIncludedByChangingCommanders=[],
        almostIncludedByAddingColorsAndChangingCommanders=[],
    )
    return response


class DiscordBotTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = await self.enterAsyncContext(FakeBackend())
        self.enterContext(patch('bot_utils.API_URL', self.backend.url))
        self.send = AsyncMock()

    async def test_query_with_one_result(self):
        self.backend.respond('GET', '/variants/', paginated_sample([
            variant_sample(id='1-2', cards=["Thassa's Oracle", 'Demonic Consultation'], results=['Win the game']),
        ]))
        reaction = await spellbook_discord.handle_queries(['oracle consultation'], self.send)
        self.assertIsNone(reaction)
        view = self.send.await_args.kwargs['view']
        self.assertIn(f"[Thassa's Oracle + Demonic Consultation]({WEBSITE_URL}/combo/1-2)", texts(view))
        self.assertIn('Win the game', texts(view))
        query = self.backend.requests[-1].query
        self.assertEqual('oracle consultation format:commander', query['q'])
        self.assertEqual(str(spellbook_discord.MAX_SEARCH_RESULTS), query['limit'])
        self.assertEqual(spellbook_discord.ORDERING, query['ordering'])

    async def test_query_with_many_results(self):
        self.backend.respond('GET', '/variants/', paginated_sample([
            variant_sample(id='1-2', cards=['A', 'B'], popularity=10),
            variant_sample(id='3-4', cards=['C', 'D'], popularity=5),
        ], count=12))
        await spellbook_discord.handle_queries(['legal:modern'], self.send)
        view = self.send.await_args.kwargs['view']
        self.assertIn('Showing 2 of 12 results for [`legal:modern`]', texts(view))
        self.assertIn('A + B ➜ Result A\n-# in 10 decks', texts(view))
        select = next(item for item in view.walk_children() if isinstance(item, spellbook_discord.VariantDetailsSelect))
        self.assertEqual(['1-2', '3-4'], [option.value for option in select.item.options])

    async def test_query_without_results(self):
        self.backend.respond('GET', '/variants/', paginated_sample([]))
        reaction = await spellbook_discord.handle_queries(['nothing'], self.send)
        self.assertIsNone(reaction)
        self.assertIn('No results found for [`nothing`]', self.send.await_args.kwargs['content'])

    async def test_invalid_query(self):
        error = sample('VariantsQueryValidationError', unexpected_fields=True)
        error['q'] = ['Unknown key: foo']
        self.backend.respond('GET', '/variants/', error, status=400)
        reaction = await spellbook_discord.handle_queries(['foo:bar'], self.send)
        self.assertEqual('⚠', reaction)
        self.assertIn('There is a problem with [`foo:bar`]', self.send.await_args.kwargs['content'])
        self.assertIn('Unknown key: foo', self.send.await_args.kwargs['content'])

    async def test_backend_failure(self):
        self.backend.respond('GET', '/variants/', {'detail': 'Server error.'}, status=500)
        reaction = await spellbook_discord.handle_queries(['a', 'b'], self.send)
        self.assertEqual('❌', reaction)
        self.assertIn('Failed to fetch results for [`a`]', self.send.await_args.kwargs['content'])
        self.assertEqual(1, self.send.await_count)

    async def test_query_too_long(self):
        reaction = await spellbook_discord.handle_queries(['x' * (spellbook_discord.MAX_QUERY_LENGTH + 1)], self.send)
        self.assertEqual('⚠', reaction)
        self.assertEqual([], self.backend.requests)

    async def test_combos_command_escapes_card_name(self):
        self.backend.respond('GET', '/variants/', paginated_sample([]))
        interaction = fake_interaction()
        await spellbook_discord.combos.callback(interaction, card='Say "Hi"')
        self.assertEqual('card="Say \\"Hi\\"" format:commander', self.backend.requests[-1].query['q'])
        interaction.followup.send.assert_awaited()

    async def test_variant_details(self):
        self.backend.respond('GET', '/variants/1-2/', variant_sample(id='1-2', cards=['A', 'B']))
        interaction = fake_interaction()
        select = spellbook_discord.VariantDetailsSelect(ui.Select(custom_id='variant-details'))
        with patch.object(ui.Select, 'values', new_callable=PropertyMock, return_value=['1-2']):
            await select.callback(interaction)
        self.assertIn('A + B', texts(interaction.followup.send.await_args.kwargs['view']))

    async def test_card_autocomplete(self):
        cards = sample('PaginatedCardDetailList', unexpected_fields=True)
        cards['results'] = [{**cards['results'][0], 'name': name} for name in ("Thassa's Oracle", 'T' * 101)]
        self.backend.respond('GET', '/cards/', cards)
        choices = await spellbook_discord.card_autocomplete(fake_interaction(), 'thassa')
        self.assertEqual(["Thassa's Oracle"], [choice.name for choice in choices])
        self.assertEqual('thassa', self.backend.requests[-1].query['q'])

    async def test_find_my_combos_from_url(self):
        deck = sample('Deck', unexpected_fields=True)
        deck['commanders'] = [{**deck['commanders'][0], 'card': 'A', 'quantity': 1}]
        deck['main'] = [{**deck['main'][0], 'card': 'B', 'quantity': 1}]
        self.backend.respond('GET', '/card-list-from-url', deck)
        self.backend.respond('POST', '/find-my-combos', find_my_combos_sample(
            included=[variant_sample(id='1-2', cards=['A', 'B'])],
            almost_included=[variant_sample(id='1-3', cards=['A', 'C'])],
        ))
        interaction = fake_interaction()
        await spellbook_discord.find_my_combos.callback(interaction, decklist='https://example.com/deck')
        self.assertEqual('https://example.com/deck', self.backend.requests[0].query['url'])
        self.assertIn('"commanders": [{"card": "A", "quantity": 1}]', self.backend.requests[1].body)
        reply = ''.join(call.kwargs['content'] for call in interaction.followup.send.await_args_list)
        self.assertIn('### 1 combos found\n', reply)
        self.assertIn(f'[A + B ➜ Result A]({WEBSITE_URL}/combo/1-2)', reply)
        self.assertIn('### 1 potential combos found\n', reply)
        self.assertIn(f'[A + C ➜ Result A]({WEBSITE_URL}/combo/1-3)', reply)

    async def test_find_my_combos_with_invalid_url(self):
        error = sample('InvalidUrlResponse', unexpected_fields=True)
        error['detail'] = 'Invalid URL'
        self.backend.respond('GET', '/card-list-from-url', error, status=400)
        interaction = fake_interaction()
        await spellbook_discord.find_my_combos.callback(interaction, decklist='https://example.com/deck')
        self.assertEqual('Invalid URL.', interaction.followup.send.await_args.kwargs['content'])

    async def test_find_my_combos_from_plain_decklist(self):
        self.backend.respond('POST', '/find-my-combos', find_my_combos_sample(included=[], almost_included=[]))
        interaction = fake_interaction()
        await spellbook_discord.handle_find_my_combos(interaction, '// Main\n1x A')
        self.assertEqual('// Main\n1x A', self.backend.requests[-1].body)
        self.assertIn('No combos found.', interaction.followup.send.await_args.kwargs['content'])

    async def test_find_my_combos_backend_failure(self):
        self.backend.respond('POST', '/find-my-combos', {'detail': 'Server error.'}, status=500)
        interaction = fake_interaction()
        await spellbook_discord.handle_find_my_combos(interaction, '// Main\n1x A')
        self.assertEqual('Failed to fetch results.', interaction.followup.send.await_args.kwargs['content'])
