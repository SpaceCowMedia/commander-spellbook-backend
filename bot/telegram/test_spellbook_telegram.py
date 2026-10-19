'''The bot against a fake backend, whose responses carry fields the client does not know about.'''
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
import telegram
from tests.fake_backend import FakeBackend
from tests.samples import sample, variant_sample, paginated_sample
from constants import WEBSITE_URL
import spellbook_telegram


class FakeMessage:
    def __init__(self, text: str = '', chat_type: str = telegram.Chat.PRIVATE):
        self.text = text
        self.chat = SimpleNamespace(type=chat_type)
        self.from_user = None
        self.replies: list[FakeMessage] = []
        self.reactions: list[str] = []

    async def reply_text(self, text: str, **_):
        reply = FakeMessage(text)
        self.replies.append(reply)
        return reply

    async def edit_text(self, text: str, **_):
        self.text = text
        return self

    async def set_reaction(self, reaction: str):
        self.reactions.append(reaction)

    async def reply_chat_action(self, _: str):
        pass


def fake_context(*args: str) -> SimpleNamespace:
    return SimpleNamespace(args=list(args), bot=SimpleNamespace(username='SpellbookBot'))


def find_my_combos_sample(included: list[dict]) -> dict:
    response = sample('PaginatedFindMyCombosResponseList', unexpected_fields=True)
    response['results'].update(
        identity='UB',
        included=included,
        includedByChangingCommanders=[],
        almostIncluded=[],
        almostIncludedByAddingColors=[],
        almostIncludedByChangingCommanders=[],
        almostIncludedByAddingColorsAndChangingCommanders=[],
    )
    return response


class TelegramBotTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = await self.enterAsyncContext(FakeBackend())
        self.enterContext(patch('bot_utils.API_URL', self.backend.url))

    async def test_query_with_one_result(self):
        self.backend.respond('GET', '/variants/', paginated_sample([variant_sample(id='1-2', cards=['A', 'B'], results=['Win'])]))
        message = FakeMessage('{{A}}')
        await spellbook_telegram.on_message(SimpleNamespace(message=message), fake_context())
        self.assertEqual(['👀', '👍'], message.reactions)
        self.assertEqual(1, len(message.replies))
        self.assertIn('**Showing 1 result for [`A`]', message.replies[0].text)
        self.assertIn(f'[A + B ➜ Win](<{WEBSITE_URL}/combo/1-2>)', message.replies[0].text)
        self.assertEqual('A format:commander', self.backend.requests[-1].query['q'])

    async def test_several_queries_share_one_reply(self):
        self.backend.respond('GET', '/variants/', paginated_sample([
            variant_sample(id='1-2', cards=['A', 'B'], identity='UB', popularity=7),
            variant_sample(id='1-3', cards=['A', 'C'], identity='R', popularity=3),
        ], count=9))
        message = FakeMessage('{{A}} and {{B}}')
        await spellbook_telegram.on_message(SimpleNamespace(message=message), fake_context())
        self.assertEqual(1, len(message.replies))
        reply = message.replies[0].text
        self.assertIn('**Showing 2 of 9 results for [`A`]', reply)
        self.assertIn('**Showing 2 of 9 results for [`B`]', reply)
        self.assertIn(f'• 🔵⚫️ [A + B ➜ Result A]({WEBSITE_URL}/combo/1-2) (in 7 decks)', reply)
        self.assertIn(f'• 🔴 [A + C ➜ Result A]({WEBSITE_URL}/combo/1-3) (in 3 decks)', reply)

    async def test_query_without_results(self):
        self.backend.respond('GET', '/variants/', paginated_sample([]))
        message = FakeMessage()
        await spellbook_telegram.search(SimpleNamespace(message=message), fake_context('nothing', 'here'))
        self.assertIn('No results found for [`nothing here`]', message.replies[0].text)

    async def test_search_without_query(self):
        message = FakeMessage()
        await spellbook_telegram.search(SimpleNamespace(message=message), fake_context())
        self.assertEqual("You haven't provided a query to search.", message.replies[0].text)
        self.assertEqual([], self.backend.requests)

    async def test_backend_failure(self):
        self.backend.respond('GET', '/variants/', {'detail': 'Server error.'}, status=500)
        message = FakeMessage('{{A}} and {{B}}')
        await spellbook_telegram.on_message(SimpleNamespace(message=message), fake_context())
        self.assertIn('👎', message.reactions)
        self.assertIn('Failed to fetch results for [`A`]', message.replies[0].text)
        self.assertEqual(1, len(self.backend.requests))

    async def test_inline_search(self):
        self.backend.respond('GET', '/variants/', paginated_sample([variant_sample(id='1-2', cards=['A', 'B'])], count=100))
        inline_query = SimpleNamespace(query='A', offset='', answer=AsyncMock())
        await spellbook_telegram.search_inline(SimpleNamespace(inline_query=inline_query), fake_context())
        results = inline_query.answer.await_args.kwargs['results']
        self.assertEqual(['Found 100 results for A', 'A + B'], [result.title for result in results])
        self.assertEqual('1-2', results[1].id)
        self.assertEqual('40', inline_query.answer.await_args.kwargs['next_offset'])

    async def test_inline_search_with_invalid_query(self):
        error = sample('VariantsQueryValidationError', unexpected_fields=True)
        error['q'] = ['Unknown key: foo']
        self.backend.respond('GET', '/variants/', error, status=400)
        inline_query = SimpleNamespace(query='foo:bar', offset='', answer=AsyncMock())
        await spellbook_telegram.search_inline(SimpleNamespace(inline_query=inline_query), fake_context())
        [result] = inline_query.answer.await_args.kwargs['results']
        self.assertEqual('Query Error', result.title)
        self.assertEqual('Unknown key: foo', result.description)

    async def test_find_my_combos_from_url(self):
        deck = sample('Deck', unexpected_fields=True)
        deck['commanders'] = [{**deck['commanders'][0], 'card': 'A', 'quantity': 1}]
        deck['main'] = [{**deck['main'][0], 'card': 'B', 'quantity': 1}]
        self.backend.respond('GET', '/card-list-from-url', deck)
        self.backend.respond('POST', '/find-my-combos', find_my_combos_sample(included=[variant_sample(id='1-2', cards=['A', 'B'])]))
        message = FakeMessage()
        await spellbook_telegram.find_my_combos(SimpleNamespace(message=message), fake_context('https://example.com/deck'))
        self.assertEqual('https://example.com/deck', self.backend.requests[0].query['url'])
        self.assertIn('"main": [{"card": "B", "quantity": 1}]', self.backend.requests[1].body)
        self.assertIn('__1 combos found__\n', message.replies[0].text)
        self.assertIn(f'[A + B ➜ Result A]({WEBSITE_URL}/combo/1-2)', message.replies[0].text)
        self.assertEqual(['👀', '👍'], message.reactions)

    async def test_find_my_combos_with_invalid_url(self):
        error = sample('InvalidUrlResponse', unexpected_fields=True)
        error['detail'] = 'Invalid URL'
        self.backend.respond('GET', '/card-list-from-url', error, status=400)
        message = FakeMessage()
        await spellbook_telegram.find_my_combos(SimpleNamespace(message=message), fake_context('https://example.com/deck'))
        self.assertEqual('Invalid URL.', message.replies[0].text)
        self.assertEqual(['👀', '👎'], message.reactions)

    async def test_find_my_combos_with_wrong_arguments(self):
        for args, answer in (
            ((), "You haven't provided a deck url."),
            (('not a url',), 'The url you have provided is not valid.'),
            (('https://a.com', 'https://b.com'), 'You have provided too many arguments.'),
        ):
            with self.subTest(args=args):
                message = FakeMessage()
                await spellbook_telegram.find_my_combos(SimpleNamespace(message=message), fake_context(*args))
                self.assertEqual(answer, message.replies[0].text)
        self.assertEqual([], self.backend.requests)
