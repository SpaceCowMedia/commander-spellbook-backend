'''The bot against a fake backend, whose responses carry fields the client does not know about.'''
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, MagicMock, patch
from tests.fake_backend import FakeBackend
from tests.samples import sample, variant_sample, paginated_sample
from constants import WEBSITE_URL
import spellbook_reddit


BOT_USERNAME = 'SpellbookBot'


async def stream(*items):
    for item in items:
        yield item


def fake_comment(body: str, author: str = 'someone', parent: MagicMock | None = None) -> MagicMock:
    comment = MagicMock()
    comment.body = body
    comment.author.name = author
    comment.reply = AsyncMock()
    comment.parent = AsyncMock(return_value=parent)
    comment.load = AsyncMock()
    return comment


class RedditBotTests(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.backend = await self.enterAsyncContext(FakeBackend())
        self.enterContext(patch('bot_utils.API_URL', self.backend.url))
        self.enterContext(patch('spellbook_reddit.REDDIT_USERNAME', BOT_USERNAME))

    async def test_text_without_queries(self):
        self.assertIsNone(await spellbook_reddit.process_input('Just chatting about combos'))
        self.assertEqual([], self.backend.requests)

    async def test_query_with_one_result(self):
        self.backend.respond('GET', '/variants/', paginated_sample([variant_sample(id='1-2', cards=['A', 'B'], results=['Win'])]))
        reply = await spellbook_reddit.process_input('Any combo with {{A}}?')
        self.assertTrue(reply.startswith(f'[A + B ➜ Win]({WEBSITE_URL}/combo/1-2)\n'))
        self.assertTrue(reply.endswith(f'Use {{{{query}}}} to search for combos. Commander Spellbook [syntax guide]({WEBSITE_URL}).'))
        query = self.backend.requests[-1].query
        self.assertEqual('A format:commander', query['q'])
        self.assertEqual(str(spellbook_reddit.MAX_SEARCH_RESULTS), query['limit'])

    async def test_query_with_more_results_than_shown(self):
        self.backend.respond('GET', '/variants/', paginated_sample([
            variant_sample(id='1-2', cards=['A', 'B'], popularity=30),
            variant_sample(id='1-3', cards=['A', 'C'], popularity=20),
        ], count=5))
        reply = await spellbook_reddit.process_input('{{A}}')
        self.assertIn('Found 5 results for [`A`]', reply)
        self.assertIn(', such as:\n', reply)
        self.assertIn(f'  1. [A + B ➜ Result A]({WEBSITE_URL}/combo/1-2) (found in 30 decks)\n', reply)
        self.assertIn(f'  1. [A + C ➜ Result A]({WEBSITE_URL}/combo/1-3) (found in 20 decks)\n', reply)
        self.assertIn('  1. [and more](', reply)

    async def test_several_queries(self):
        self.backend.respond('GET', '/variants/', paginated_sample([]))
        reply = await spellbook_reddit.process_input('{{A}} or {{B}}')
        self.assertIn('* No results found for [`A`]', reply)
        self.assertIn('* No results found for [`B`]', reply)

    async def test_backend_failure(self):
        self.backend.respond('GET', '/variants/', {'detail': 'Server error.'}, status=500)
        reply = await spellbook_reddit.process_input('{{A}}')
        self.assertTrue(reply.startswith('Failed to fetch results for [`A`]'))

    async def test_comments_are_answered(self):
        self.backend.respond('GET', '/variants/', paginated_sample([]))
        comment = fake_comment('{{A}}')
        own_comment = fake_comment('{{B}}', author=BOT_USERNAME)
        subreddit = MagicMock()
        subreddit.stream.comments = lambda **_: stream(comment, own_comment)
        reddit = MagicMock(subreddit=AsyncMock(return_value=subreddit))
        await spellbook_reddit.process_comments(reddit)
        self.assertIn('No results found for [`A`]', comment.reply.await_args.args[0])
        own_comment.reply.assert_not_awaited()
        self.assertEqual(['A format:commander'], [request.query['q'] for request in self.backend.requests])

    async def test_greetings(self):
        own_answer = fake_comment('Found 2 results', author=BOT_USERNAME)
        for body, responses in (('Good bot', spellbook_reddit.GOOD_BOT_RESPONSES), ('thank you!', spellbook_reddit.THANKS_RESPONSES)):
            with self.subTest(body=body):
                comment = fake_comment(body, parent=own_answer)
                await spellbook_reddit.answer_greeting(comment)
                self.assertIn(comment.reply.await_args.args[0], responses)

    async def test_greetings_to_someone_else(self):
        comment = fake_comment('Good bot', parent=fake_comment('I am not a bot'))
        await spellbook_reddit.answer_greeting(comment)
        comment.reply.assert_not_awaited()

    async def test_daily_combo(self):
        combo_of_the_day = sample('WebsiteProperty', unexpected_fields=True)
        combo_of_the_day.update(key='combo_of_the_day', value='1-2')
        self.backend.respond('GET', '/properties/combo_of_the_day/', combo_of_the_day)
        self.backend.respond('GET', '/variants/1-2/', variant_sample(id='1-2', cards=['A', 'B'], results=['Win'], spoiler=True))
        submission = MagicMock(reply=AsyncMock())
        subreddit = MagicMock(submit=AsyncMock(return_value=submission))
        reddit = MagicMock(subreddit=AsyncMock(return_value=subreddit))
        await spellbook_reddit.post_daily_combo(reddit)
        reddit.subreddit.assert_awaited_with(spellbook_reddit.MAIN_SUBREDDIT)
        self.assertEqual(f'{WEBSITE_URL}/combo/1-2', subreddit.submit.await_args.kwargs['url'])
        self.assertTrue(subreddit.submit.await_args.kwargs['spoiler'])
        comment = submission.reply.await_args.args[0]
        self.assertIn('### Cards\n\n* A\n* B\n', comment)
        self.assertIn('### Results\n\n* Win\n', comment)

    async def test_daily_combo_backend_failure(self):
        self.backend.respond('GET', '/properties/combo_of_the_day/', {'detail': 'Server error.'}, status=500)
        reddit = MagicMock(subreddit=AsyncMock())
        with self.assertLogs(spellbook_reddit.LOGGER, 'ERROR'):
            await spellbook_reddit.post_daily_combo(reddit)
        reddit.subreddit.assert_not_awaited()
